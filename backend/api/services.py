"""
Orchestration helpers for the HTTP API.

All crowd mathematics, risk scoring, pathfinding, and ML prediction are
delegated to the existing ``simulation`` and ``prediction`` packages.
This module only shapes inputs/outputs for JSON transport.
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from prediction.features import engineer_features
from prediction.predictor import calculate_risk, load_model, predict_bottleneck
from prediction.risk_engine import calculate_risk as rule_risk
from simulation.crowd_simulator import CrowdSimulator
from simulation.scenario_generator import VENUE_BUILDERS
from simulation.utils import DEFAULT_CONFIG, ScenarioType, get_logger, risk_level_from_score

logger = get_logger(__name__)

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_MODEL_PATH = os.path.join(BACKEND_ROOT, "data", "models", "model.joblib")

_LAST_RUN: Dict[str, Any] = {}
_MODEL_READY = False
_MODEL_ERROR: Optional[str] = None


def list_venues() -> List[Dict[str, str]]:
    return [
        {"id": key, "name": key.replace("_", " ").title()}
        for key in VENUE_BUILDERS.keys()
    ]


def list_scenarios() -> List[Dict[str, str]]:
    return [
        {"id": s.value, "name": s.value.replace("_", " ").title()}
        for s in ScenarioType
    ]


def _resolve_arrival_rate(
    arrival_rate: Optional[float],
    expected_crowd_size: Optional[int],
    duration_seconds: int,
    event_schedule: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Map PDF inputs (expected crowd size + event schedule) onto the existing
    simulator's base_arrival_rate without changing simulation mathematics.
    """
    timestep = DEFAULT_CONFIG.timestep_seconds
    _ = timestep  # retained for future step-based mappings

    peak_factor = 1.0
    if event_schedule:
        peak_mins = float(event_schedule.get("peak_window_minutes") or 30)
        event_mins = float(event_schedule.get("event_duration_minutes") or 120)
        # Shorter peak window relative to event => higher arrival intensity.
        peak_factor = min(4.0, max(1.0, (event_mins / max(peak_mins, 1.0)) * 0.35 + 0.65))

    if arrival_rate is not None:
        # Explicit operator rate still respects mild schedule intensity.
        return min(80.0, max(0.0, float(arrival_rate) * (1.0 + (peak_factor - 1.0) * 0.35)))

    if expected_crowd_size is not None and int(expected_crowd_size) > 0:
        # Map PDF expected crowd onto practical arrival pressure.
        # The discrete simulator is zone-aggregate; we scale relative to a
        # 10k reference rather than spawning one agent per person.
        reference = 10000.0
        scale = float(expected_crowd_size) / reference
        base = float(DEFAULT_CONFIG.base_arrival_rate) * max(scale, 0.25)
        return min(60.0, max(0.5, base * peak_factor))

    return min(60.0, float(DEFAULT_CONFIG.base_arrival_rate) * peak_factor)


def _build_sim(
    venue: str,
    duration_seconds: int,
    random_seed: Optional[int] = 42,
    arrival_rate: Optional[float] = None,
) -> CrowdSimulator:
    builder = VENUE_BUILDERS.get(venue)
    if builder is None:
        raise ValueError(f"Unknown venue '{venue}'. Available: {list(VENUE_BUILDERS)}")

    kwargs: Dict[str, Any] = {
        "timestep_seconds": DEFAULT_CONFIG.timestep_seconds,
        "total_duration_seconds": duration_seconds,
        "random_seed": random_seed,
    }
    if arrival_rate is not None:
        kwargs["base_arrival_rate"] = float(arrival_rate)

    config = replace(DEFAULT_CONFIG, **kwargs)
    return builder(config)


def _neighbor_lookup(sim: CrowdSimulator) -> Dict[str, List[str]]:
    return {zid: list(zone.neighbors) for zid, zone in sim.zones.items()}


ZONE_TYPE_LABELS = {
    "gate": "Entry Gate",
    "entry": "Entry Gate",
    "corridor": "Walkway / Corridor",
    "waiting_area": "Concourse / Waiting",
    "food_court": "Concession / Food",
    "event_zone": "Event Zone",
    "exit": "Emergency Exit",
}


def _graph_payload(sim: CrowdSimulator) -> Dict[str, Any]:
    nodes = []
    edges = []
    seen_edges = set()
    for zid, zone in sim.zones.items():
        zt = zone.zone_type.value
        nodes.append(
            {
                "id": zid,
                "zone_type": zt,
                "zone_label": ZONE_TYPE_LABELS.get(zt, zt.replace("_", " ").title()),
                "capacity": zone.capacity,
                "area_sqm": zone.area_sqm,
                "neighbors": list(zone.neighbors),
            }
        )
        for nb in zone.neighbors:
            edge_key = tuple(sorted((zid, nb)))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({"source": edge_key[0], "target": edge_key[1]})
    return {
        "nodes": nodes,
        "edges": edges,
        "gates": list(sim.gates),
        "exits": list(sim.exits),
        "food_courts": list(sim.food_courts),
        "event_zones": list(sim.event_zones),
        "legend": [
            {"zone_type": k, "label": v}
            for k, v in ZONE_TYPE_LABELS.items()
        ],
    }


def _latest_snapshot(records: List[dict]) -> List[dict]:
    if not records:
        return []
    max_ts = max(r["timestamp"] for r in records)
    return [r for r in records if r["timestamp"] == max_ts]


def _is_critical_bottleneck(pred: Optional[dict]) -> bool:
    if not pred:
        return False
    level = (pred.get("risk_level") or "").upper()
    proba = pred.get("bottleneck_probability")
    density = pred.get("predicted_density")
    if level in ("HIGH", "CRITICAL"):
        return True
    if proba is not None and float(proba) >= 0.5:
        return True
    if density is not None and float(density) >= 1.0:
        return True
    return False


def _enrich_zones(
    snapshot: List[dict],
    history_df: pd.DataFrame,
    neighbor_lookup: Dict[str, List[str]],
    model_available: bool,
) -> Tuple[List[dict], List[dict], Optional[dict]]:
    engineered = engineer_features(history_df, neighbor_lookup=neighbor_lookup)
    latest_ts = engineered["timestamp"].max()
    latest_eng = engineered[engineered["timestamp"] == latest_ts]

    zones_out: List[dict] = []
    predictions: List[dict] = []
    bottleneck: Optional[dict] = None

    for _, row in latest_eng.iterrows():
        state = row.to_dict()
        risk = calculate_risk(state)
        zone_payload = {
            "zone": state["zone"],
            "zone_type": next(
                (s.get("zone_type") for s in snapshot if s["zone"] == state["zone"]),
                "unknown",
            ),
            "people_count": int(state["people_count"]),
            "capacity": int(state["capacity"]),
            "density": float(state["density"]),
            "inflow": int(state["inflow"]),
            "outflow": int(state["outflow"]),
            "avg_speed": float(state["avg_speed"]),
            "timestamp": int(state["timestamp"]),
            "capacity_utilization": float(state.get("capacity_utilization", state["density"])),
            "flow_imbalance": float(state.get("flow_imbalance", 0.0)),
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "status": risk["risk_level"],
        }
        zones_out.append(zone_payload)

        pred: Dict[str, Any] = {
            "zone": state["zone"],
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "predicted_density": None,
            "bottleneck_probability": None,
            "time_to_bottleneck": None,
            "model_available": model_available,
        }
        if model_available:
            try:
                ml = predict_bottleneck(state, model_path=DEFAULT_MODEL_PATH)
                pred.update(
                    {
                        "predicted_density": ml.get("predicted_density"),
                        "bottleneck_probability": ml.get("bottleneck_probability"),
                        "time_to_bottleneck": ml.get("time_to_bottleneck"),
                        "risk_score": ml.get("risk_score", risk["risk_score"]),
                        "risk_level": ml.get("risk_level", risk["risk_level"]),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("ML prediction failed for %s: %s", state["zone"], exc)

        predictions.append(pred)

        if bottleneck is None or (pred.get("risk_score") or 0) > (bottleneck.get("risk_score") or 0):
            bottleneck = dict(pred)

    zones_out.sort(key=lambda z: z["risk_score"], reverse=True)
    predictions.sort(key=lambda p: p.get("risk_score") or 0, reverse=True)
    if bottleneck:
        bottleneck["is_critical"] = _is_critical_bottleneck(bottleneck)
    return zones_out, predictions, bottleneck


def _density_forecast(
    records: List[dict],
    zones_latest: List[dict],
    bottleneck: Optional[dict],
    timestep_seconds: int,
) -> List[dict]:
    by_ts: Dict[int, List[float]] = defaultdict(list)
    for r in records:
        by_ts[int(r["timestamp"])].append(float(r["density"]))

    risk_by_zone = {z["zone"]: z["risk_score"] for z in zones_latest}
    points = []
    for ts in sorted(by_ts.keys()):
        dens = sum(by_ts[ts]) / len(by_ts[ts])
        points.append(
            {
                "timestamp": ts,
                "label": f"{ts // 60}m" if ts > 0 else "Now",
                "density_pct": round(dens * 100.0, 2),
                "predicted_density_pct": None,
                "risk_score": None,
                "minutes": round(ts / 60.0, 2),
                "is_prediction": False,
            }
        )

    if len(points) > 12:
        step = max(1, len(points) // 12)
        sampled = points[::step][-12:]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        points = sampled

    if points:
        end_ts = points[-1]["timestamp"]
        overall_risk = max((z["risk_score"] for z in zones_latest), default=0)
        for p in points:
            delta_min = (p["timestamp"] - end_ts) / 60.0
            p["label"] = "Now" if abs(delta_min) < 1e-6 else f"{int(delta_min)}m"
            p["risk_score"] = overall_risk

        if bottleneck and bottleneck.get("predicted_density") is not None:
            pred_pct = round(float(bottleneck["predicted_density"]) * 100.0, 2)
            points[-1]["predicted_density_pct"] = pred_pct
            points.append(
                {
                    "timestamp": end_ts + timestep_seconds * 3,
                    "label": "+pred",
                    "density_pct": None,
                    "predicted_density_pct": pred_pct,
                    "risk_score": bottleneck.get("risk_score"),
                    "minutes": round((end_ts + timestep_seconds * 3) / 60.0, 2),
                    "is_prediction": True,
                }
            )
        _ = risk_by_zone
    return points


def _aggregate_stats(zones: List[dict], timestep_seconds: int) -> Dict[str, Any]:
    if not zones:
        return {
            "total_crowd": 0,
            "avg_density": 0.0,
            "total_inflow": 0,
            "total_outflow": 0,
            "inflow_per_min": 0.0,
            "outflow_per_min": 0.0,
            "mean_risk_score": 0,
            "overall_risk_score": 0,
            "overall_risk_level": "LOW",
            "active_alerts": 0,
        }
    total_crowd = sum(z["people_count"] for z in zones)
    avg_density = sum(z["density"] for z in zones) / len(zones)
    total_inflow = sum(z["inflow"] for z in zones)
    total_outflow = sum(z["outflow"] for z in zones)
    mean_risk = int(round(sum(z["risk_score"] for z in zones) / len(zones)))
    overall = max(zones, key=lambda z: z["risk_score"])
    minutes = max(timestep_seconds / 60.0, 1e-6)
    alerts = sum(1 for z in zones if z["risk_level"] in ("HIGH", "CRITICAL"))
    return {
        "total_crowd": total_crowd,
        "avg_density": round(avg_density, 4),
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
        "inflow_per_min": round(total_inflow / minutes, 2),
        "outflow_per_min": round(total_outflow / minutes, 2),
        "mean_risk_score": mean_risk,
        "overall_risk_score": overall["risk_score"],
        "overall_risk_level": overall["risk_level"],
        "active_alerts": alerts,
    }


def model_is_available() -> bool:
    return _MODEL_READY


def health_payload() -> Dict[str, Any]:
    try:
        from vision.hf_detector import hf_config_status
        hf = hf_config_status()
    except Exception as exc:  # noqa: BLE001
        hf = {"configured": False, "message": str(exc)}
    return {
        "status": "ok",
        "model_available": _MODEL_READY,
        "model_loaded": _MODEL_READY,
        "model_path": DEFAULT_MODEL_PATH if _MODEL_READY else None,
        "model_error": _MODEL_ERROR,
        "simulator_ready": True,
        "huggingface": hf,
        "venues": list(VENUE_BUILDERS.keys()),
        "scenarios": [s.value for s in ScenarioType],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def try_warm_model() -> bool:
    global _MODEL_READY, _MODEL_ERROR
    if not os.path.exists(DEFAULT_MODEL_PATH):
        _MODEL_READY = False
        _MODEL_ERROR = f"No model file at {DEFAULT_MODEL_PATH}"
        return False
    try:
        load_model(DEFAULT_MODEL_PATH, force_reload=True)
        _MODEL_READY = True
        _MODEL_ERROR = None
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not warm model: %s", exc)
        _MODEL_READY = False
        _MODEL_ERROR = str(exc)
        return False


def get_venue_graph(venue: str) -> Dict[str, Any]:
    sim = _build_sim(venue, duration_seconds=60, random_seed=0)
    return {"venue": venue, "graph": _graph_payload(sim)}


def _compose_result(
    venue: str,
    scenario: str,
    duration_seconds: int,
    random_seed: int,
    arrival_rate: float,
    sim: CrowdSimulator,
    records: List[dict],
    expected_crowd_size: Optional[int] = None,
    event_schedule: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    snapshot = _latest_snapshot(records)
    df = pd.DataFrame(records)
    neighbors = _neighbor_lookup(sim)
    ml_ok = model_is_available()
    zones, predictions, bottleneck = _enrich_zones(snapshot, df, neighbors, ml_ok)
    stats = _aggregate_stats(zones, sim.config.timestep_seconds)
    forecast = _density_forecast(records, zones, bottleneck, sim.config.timestep_seconds)
    timestamp = max((z["timestamp"] for z in zones), default=0)

    return {
        "venue": venue,
        "scenario": scenario,
        "duration_seconds": duration_seconds,
        "timestep_seconds": sim.config.timestep_seconds,
        "random_seed": random_seed,
        "arrival_rate": arrival_rate,
        "expected_crowd_size": expected_crowd_size,
        "event_schedule": event_schedule,
        "timestamp": timestamp,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "model_available": ml_ok,
        "total_people": stats["total_crowd"],
        "stats": stats,
        "zones": zones,
        "predictions": predictions,
        "bottleneck": bottleneck,
        "forecast": forecast,
        "graph": _graph_payload(sim),
        "high_risk_zones": [
            {"zone": z["zone"], "risk_score": z["risk_score"], "risk_level": z["risk_level"]}
            for z in zones
            if z["risk_level"] in ("HIGH", "CRITICAL")
        ],
    }


def _execute_simulation(
    venue: str,
    scenario: str,
    duration_seconds: int,
    random_seed: int,
    arrival_rate: Optional[float],
    expected_crowd_size: Optional[int] = None,
    event_schedule: Optional[Dict[str, Any]] = None,
) -> Tuple[CrowdSimulator, List[dict], Dict[str, Any]]:
    resolved_rate = _resolve_arrival_rate(
        arrival_rate=arrival_rate,
        expected_crowd_size=expected_crowd_size,
        duration_seconds=duration_seconds,
        event_schedule=event_schedule,
    )
    sim = _build_sim(venue, duration_seconds, random_seed=random_seed, arrival_rate=resolved_rate)
    records = sim.run(scenario=scenario, duration_seconds=duration_seconds)
    result = _compose_result(
        venue,
        scenario,
        duration_seconds,
        random_seed,
        resolved_rate,
        sim,
        records,
        expected_crowd_size=expected_crowd_size,
        event_schedule=event_schedule,
    )
    return sim, records, result


def _store_last_run(request: Dict[str, Any], result: Dict[str, Any], records: List[dict]) -> None:
    _LAST_RUN.clear()
    _LAST_RUN.update(
        {
            "request": request,
            "result": result,
            "records": records,
            "zones_state": {z["zone"]: z for z in result["zones"]},
        }
    )


def run_simulation(
    venue: str,
    scenario: str,
    duration_seconds: int = 600,
    random_seed: int = 42,
    arrival_rate: Optional[float] = None,
    expected_crowd_size: Optional[int] = None,
    event_schedule: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    valid_scenarios = {s.value for s in ScenarioType}
    if scenario not in valid_scenarios:
        raise ValueError(f"Unknown scenario '{scenario}'. Available: {sorted(valid_scenarios)}")

    # If operator provides event duration and did not customize sim length beyond default,
    # allow schedule to influence duration modestly (cap for demo performance).
    schedule = dict(event_schedule or {})
    if schedule.get("event_duration_minutes") and duration_seconds == 600:
        # Map event minutes to a bounded simulation window for responsiveness.
        duration_seconds = int(min(1800, max(120, int(schedule["event_duration_minutes"]) * 2)))

    _, records, result = _execute_simulation(
        venue,
        scenario,
        duration_seconds,
        random_seed,
        arrival_rate,
        expected_crowd_size=expected_crowd_size,
        event_schedule=schedule or None,
    )
    _store_last_run(
        {
            "venue": venue,
            "scenario": scenario,
            "duration_seconds": duration_seconds,
            "random_seed": random_seed,
            "arrival_rate": result["arrival_rate"],
            "expected_crowd_size": expected_crowd_size,
            "event_schedule": schedule or None,
        },
        result,
        records,
    )
    return result


def _path_metrics(sim: CrowdSimulator, path: List[str], zone_state: Dict[str, dict]) -> Dict[str, Any]:
    risks = []
    distance_m = 0.0
    for idx, zid in enumerate(path):
        if zid in zone_state:
            risks.append(int(zone_state[zid]["risk_score"]))
            speed = float(zone_state[zid].get("avg_speed") or DEFAULT_CONFIG.base_walk_speed_mps)
        else:
            risks.append(
                rule_risk(
                    {"density": 0.0, "capacity": sim.zones[zid].capacity, "avg_speed": 1.4}
                )["risk_score"]
            )
            speed = DEFAULT_CONFIG.base_walk_speed_mps
        if idx < len(path) - 1:
            # Approximate segment length from zone floor area (existing area_sqm).
            distance_m += math.sqrt(max(sim.zones[zid].area_sqm, 1.0))

    avg_risk = int(round(sum(risks) / len(risks))) if risks else 0
    hops = max(0, len(path) - 1)
    avg_speed = DEFAULT_CONFIG.base_walk_speed_mps
    if zone_state:
        speeds = [float(zone_state[z]["avg_speed"]) for z in path if z in zone_state]
        if speeds:
            avg_speed = max(sum(speeds) / len(speeds), DEFAULT_CONFIG.min_speed_mps)
    travel_time_s = int(round(distance_m / avg_speed)) if avg_speed > 0 else None

    return {
        "path": path,
        "hops": hops,
        "distance_m": int(round(distance_m)),
        "travel_time_s": travel_time_s,
        "risk_score": avg_risk,
        "risk_level": risk_level_from_score(avg_risk).value,
        "zone_risks": [{"zone": z, "risk_score": r} for z, r in zip(path, risks)],
    }


def find_routes(venue: str, source: str, target: str, max_alternates: int = 3) -> Dict[str, Any]:
    """
    Expose simulator BFS pathfinding. A path is valid only if it reaches
    ``target`` (``path[-1] == target``). ``[start]`` alone is valid only when
    ``source == target``.
    """
    sim = _build_sim(venue, duration_seconds=60, random_seed=0)
    if source not in sim.zones or target not in sim.zones:
        raise ValueError(f"Unknown zone(s). Available: {sorted(sim.zones.keys())}")

    zone_state = (
        (_LAST_RUN.get("zones_state") or {})
        if _LAST_RUN.get("request", {}).get("venue") == venue
        else {}
    )

    def is_valid(path: Optional[List[str]]) -> bool:
        if not path:
            return False
        if source == target:
            return path == [source]
        return len(path) > 1 and path[0] == source and path[-1] == target

    primary = sim._shortest_path(source, target)  # noqa: SLF001
    routes: List[dict] = []
    if is_valid(primary):
        routes.append(_path_metrics(sim, primary, zone_state))

    if is_valid(primary) and len(primary) > 1 and max_alternates > 1:
        for i in range(len(primary) - 1):
            a, b = primary[i], primary[i + 1]
            removed_ab = False
            removed_ba = False
            if b in sim.zones[a].neighbors:
                sim.zones[a].neighbors.remove(b)
                removed_ab = True
            if a in sim.zones[b].neighbors:
                sim.zones[b].neighbors.remove(a)
                removed_ba = True
            alt = sim._shortest_path(source, target)  # noqa: SLF001
            if removed_ab and b not in sim.zones[a].neighbors:
                sim.zones[a].neighbors.append(b)
            if removed_ba and a not in sim.zones[b].neighbors:
                sim.zones[b].neighbors.append(a)
            if is_valid(alt) and alt != primary and all(r["path"] != alt for r in routes):
                routes.append(_path_metrics(sim, alt, zone_state))
            if len(routes) >= max_alternates:
                break

    recommended = min(routes, key=lambda r: (r["risk_score"], r["hops"])) if routes else None
    status = "ok" if recommended else "no_route"
    return {
        "status": status,
        "venue": venue,
        "source": source,
        "destination": target,
        "target": target,
        "routes": routes,
        "recommended": recommended,
        "message": None if recommended else "NO SAFE ROUTE FOUND",
    }


def _derive_redirect_percentage(busiest: dict, gate_states: List[dict]) -> Optional[int]:
    weights = [max(0, z["inflow"]) + max(0, z["people_count"]) for z in gate_states]
    total_w = sum(weights)
    if total_w > 0:
        pct = int(round(100.0 * (busiest["inflow"] + busiest["people_count"]) / total_w))
    else:
        dens = float(busiest.get("density") or 0.0)
        if dens <= 0:
            return None
        pct = int(round(dens * 100))
    pct = max(10, min(50, pct))
    return pct


def _build_intervention_proposal(result: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    zones = result.get("zones") or []
    graph = result.get("graph") or {}
    bottleneck = result.get("bottleneck")
    if not zones:
        return {
            "status": "unavailable",
            "message": "No zone data available for intervention.",
            "recommended_action": None,
        }

    if not bottleneck:
        bottleneck = zones[0]

    gates = graph.get("gates") or []
    gate_states = [z for z in zones if z["zone"] in gates]

    action: Optional[Dict[str, Any]] = None
    reason = None

    if len(gates) >= 2 and len(gate_states) >= 2:
        busiest = max(
            gate_states,
            key=lambda z: (z["inflow"] + z["people_count"], z["density"], z["risk_score"]),
        )
        alternatives = [z for z in gate_states if z["zone"] != busiest["zone"]]
        if not alternatives:
            return {
                "status": "no_alternative",
                "message": "No alternative gate available",
                "detected_bottleneck": bottleneck.get("zone"),
                "current_risk_score": int(bottleneck.get("risk_score") or 0),
                "current_risk_level": bottleneck.get("risk_level"),
                "recommended_action": None,
            }
        quietest = min(
            alternatives,
            key=lambda z: (z["inflow"] + z["people_count"], z["density"], z["risk_score"]),
        )
        pct = _derive_redirect_percentage(busiest, gate_states)
        if pct is None:
            pct = 20
        action = {
            "type": "REDIRECT",
            "action": "REDIRECT",
            "description": f"Redirect traffic {busiest['zone']} -> {quietest['zone']}",
            "source": busiest["zone"],
            "target": quietest["zone"],
            "from_gate": busiest["zone"],
            "to_gate": quietest["zone"],
            "percentage": pct,
            "redirect_percentage": pct,
        }
        reason = (
            f"Reduces inflow pressure toward predicted bottleneck "
            f"'{bottleneck.get('zone')}' by shifting arrivals from "
            f"{busiest['zone']} toward {quietest['zone']}."
        )
    elif gates:
        dens = float(bottleneck.get("predicted_density") or zones[0]["density"] or 0.2)
        pct = max(10, min(50, int(round(dens * 40)) or 20))
        action = {
            "type": "REDUCE_ARRIVALS",
            "action": "REDUCE_ARRIVALS",
            "description": "Reduce overall gate arrivals (single-gate venue)",
            "source": gates[0],
            "target": None,
            "from_gate": gates[0],
            "to_gate": None,
            "percentage": pct,
            "redirect_percentage": pct,
        }
        reason = (
            f"Single-gate venue: reduce arrival rate to relieve bottleneck "
            f"'{bottleneck.get('zone')}'."
        )
    else:
        return {
            "status": "unavailable",
            "message": "No gates available for intervention.",
            "detected_bottleneck": bottleneck.get("zone"),
            "recommended_action": None,
        }

    return {
        "status": "proposed",
        "venue": request["venue"],
        "scenario": request["scenario"],
        "detected_bottleneck": bottleneck.get("zone"),
        "current_risk_score": int(bottleneck.get("risk_score") or 0),
        "current_risk_level": bottleneck.get("risk_level"),
        "recommended_action": action,
        "reason": reason,
        "time_to_bottleneck": bottleneck.get("time_to_bottleneck"),
        "predicted_density": bottleneck.get("predicted_density"),
        "bottleneck_probability": bottleneck.get("bottleneck_probability"),
    }


def recommend_intervention() -> Dict[str, Any]:
    if not _LAST_RUN.get("result"):
        raise RuntimeError("No simulation has been run yet. Call /api/simulation first.")
    return _build_intervention_proposal(_LAST_RUN["result"], _LAST_RUN["request"])


def _risk_tuple(result: Dict[str, Any]) -> Tuple[int, int]:
    stats = result["stats"]
    return int(stats["overall_risk_score"]), int(stats.get("mean_risk_score") or stats["overall_risk_score"])


def simulate_intervention(redirect_percentage: Optional[int] = None) -> Dict[str, Any]:
    """
    Evaluate candidate arrival reductions. Accept only if overall risk
    decreases versus the baseline. Restore baseline state when rejected.
    """
    if not _LAST_RUN.get("result"):
        raise RuntimeError("No simulation has been run yet. Call /api/simulation first.")

    request = dict(_LAST_RUN["request"])
    before = _LAST_RUN["result"]
    before_records = _LAST_RUN.get("records") or []
    proposal = _build_intervention_proposal(before, request)

    if not proposal.get("recommended_action"):
        return {
            "status": "rejected",
            "message": proposal.get("message") or "No beneficial intervention found",
            "recommendation": proposal,
            "beneficial": False,
            "before": {
                "risk_score": before["stats"]["overall_risk_score"],
                "risk_level": before["stats"]["overall_risk_level"],
                "stats": before["stats"],
                "bottleneck": before.get("bottleneck"),
            },
            "after": None,
            "change": None,
        }

    action = proposal["recommended_action"]
    if redirect_percentage is not None:
        candidates = [max(5, min(80, int(redirect_percentage)))]
    else:
        base_pct = int(action.get("percentage") or action.get("redirect_percentage") or 20)
        candidates = sorted({max(10, base_pct - 10), base_pct, min(50, base_pct + 10), 25, 35})

    original_rate = float(request.get("arrival_rate") or DEFAULT_CONFIG.base_arrival_rate)
    before_overall, before_mean = _risk_tuple(before)

    best: Optional[Dict[str, Any]] = None
    evaluations = []

    for pct in candidates:
        reduced_rate = original_rate * (1.0 - pct / 100.0)
        _, records, after = _execute_simulation(
            venue=request["venue"],
            scenario=request["scenario"],
            duration_seconds=request["duration_seconds"],
            random_seed=request.get("random_seed", 42),
            arrival_rate=reduced_rate,
        )
        after_overall, after_mean = _risk_tuple(after)
        improves = after_overall < before_overall or (
            after_overall == before_overall and after_mean < before_mean
        )
        evaluations.append(
            {
                "percentage": pct,
                "risk_before": before_overall,
                "risk_after": after_overall,
                "mean_risk_before": before_mean,
                "mean_risk_after": after_mean,
                "improves": improves,
            }
        )
        if improves:
            score = (after_overall, after_mean, pct)
            if best is None or score < best["score"]:
                best = {
                    "score": score,
                    "pct": pct,
                    "after": after,
                    "records": records,
                }

    if best is None:
        # Restore baseline — ephemeral evaluations must not replace last run.
        _store_last_run(request, before, before_records)
        return {
            "status": "rejected",
            "message": "No beneficial intervention found",
            "beneficial": False,
            "recommendation": proposal,
            "redirect_percentage_applied": None,
            "evaluations": evaluations,
            "reason": proposal.get("reason"),
            "before": {
                "risk_score": before_overall,
                "risk_level": before["stats"]["overall_risk_level"],
                "stats": before["stats"],
                "bottleneck": before.get("bottleneck"),
            },
            "after": None,
            "change": None,
            "risk_before": before_overall,
            "risk_after": None,
        }

    after = best["after"]
    pct = best["pct"]
    after_overall = after["stats"]["overall_risk_score"]
    reduction_pct = (
        round(100.0 * (before_overall - after_overall) / before_overall, 1)
        if before_overall > 0
        else 0.0
    )

    # Persist improved state as the new operational snapshot.
    _store_last_run(
        {**request, "arrival_rate": after["arrival_rate"]},
        after,
        best["records"],
    )

    applied_action = dict(action)
    applied_action["percentage"] = pct
    applied_action["redirect_percentage"] = pct

    return {
        "status": "applied",
        "beneficial": True,
        "message": "Intervention improves crowd distribution",
        "recommendation": {**proposal, "recommended_action": applied_action},
        "redirect_percentage_applied": pct,
        "evaluations": evaluations,
        "reason": proposal.get("reason"),
        "source": applied_action.get("source"),
        "target": applied_action.get("target"),
        "percentage": pct,
        "risk_before": before_overall,
        "risk_after": after_overall,
        "before": {
            "risk_score": before_overall,
            "risk_level": before["stats"]["overall_risk_level"],
            "stats": before["stats"],
            "bottleneck": before.get("bottleneck"),
            "total_crowd": before["stats"]["total_crowd"],
            "avg_density": before["stats"]["avg_density"],
        },
        "after": {
            "risk_score": after_overall,
            "risk_level": after["stats"]["overall_risk_level"],
            "stats": after["stats"],
            "bottleneck": after.get("bottleneck"),
            "zones": after["zones"],
            "forecast": after["forecast"],
            "graph": after["graph"],
            "predictions": after["predictions"],
            "high_risk_zones": after["high_risk_zones"],
            "total_crowd": after["stats"]["total_crowd"],
            "avg_density": after["stats"]["avg_density"],
        },
        "change": {
            "risk_delta": after_overall - before_overall,
            "risk_reduction_pct": reduction_pct,
            "crowd_delta": after["stats"]["total_crowd"] - before["stats"]["total_crowd"],
            "density_delta": round(
                after["stats"]["avg_density"] - before["stats"]["avg_density"], 4
            ),
        },
    }


def run_what_if(test_arrival_rate: float) -> Dict[str, Any]:
    if not _LAST_RUN.get("request"):
        raise RuntimeError("No simulation has been run yet. Call /api/simulation first.")

    request = dict(_LAST_RUN["request"])
    current = _LAST_RUN["result"]
    current_records = _LAST_RUN.get("records") or []

    _, _, alt = _execute_simulation(
        venue=request["venue"],
        scenario=request["scenario"],
        duration_seconds=request["duration_seconds"],
        random_seed=request.get("random_seed", 42),
        arrival_rate=float(test_arrival_rate),
    )

    # What-if is exploratory — restore baseline operational state.
    _store_last_run(request, current, current_records)

    cur_eta = (current.get("bottleneck") or {}).get("time_to_bottleneck")
    alt_eta = (alt.get("bottleneck") or {}).get("time_to_bottleneck")
    cur_density = current["stats"]["avg_density"]
    alt_density = alt["stats"]["avg_density"]

    return {
        "status": "ok",
        "baseline": {
            "arrival_rate": request.get("arrival_rate"),
            "scenario": request.get("scenario"),
            "risk_score": current["stats"]["overall_risk_score"],
            "risk_level": current["stats"]["overall_risk_level"],
            "density": cur_density,
            "time_to_bottleneck": cur_eta,
            "stats": current["stats"],
        },
        "current": {
            "arrival_rate": request.get("arrival_rate"),
            "risk_score": current["stats"]["overall_risk_score"],
            "risk_level": current["stats"]["overall_risk_level"],
            "time_to_bottleneck": cur_eta,
            "stats": current["stats"],
            "density": cur_density,
        },
        "scenario": {
            "arrival_rate": float(test_arrival_rate),
            "risk_score": alt["stats"]["overall_risk_score"],
            "risk_level": alt["stats"]["overall_risk_level"],
            "density": alt_density,
            "time_to_bottleneck": alt_eta,
            "stats": alt["stats"],
        },
        "what_if": {
            "arrival_rate": float(test_arrival_rate),
            "risk_score": alt["stats"]["overall_risk_score"],
            "risk_level": alt["stats"]["overall_risk_level"],
            "time_to_bottleneck": alt_eta,
            "stats": alt["stats"],
            "zones": alt["zones"],
            "bottleneck": alt.get("bottleneck"),
            "forecast": alt["forecast"],
            "high_risk_zones": alt["high_risk_zones"],
            "density": alt_density,
        },
        "comparison": {
            "risk_change": alt["stats"]["overall_risk_score"] - current["stats"]["overall_risk_score"],
            "density_change": round(alt_density - cur_density, 4),
            "eta_change": (
                None
                if cur_eta is None or alt_eta is None
                else round(float(alt_eta) - float(cur_eta), 2)
            ),
        },
        "change": {
            "risk_delta": alt["stats"]["overall_risk_score"] - current["stats"]["overall_risk_score"],
            "density_delta": round(alt_density - cur_density, 4),
            "eta_delta": (
                None
                if cur_eta is None or alt_eta is None
                else round(float(alt_eta) - float(cur_eta), 2)
            ),
        },
    }
