"""
risk_engine.py

Rule-based (non-ML) congestion risk scoring. Produces a 0-100 risk
score and a discrete risk level (LOW / MEDIUM / HIGH / CRITICAL) from
a zone's current state. This runs independently of the ML models so
the system always has a real-time risk estimate, even before/without
a trained model.
"""

from __future__ import annotations

from typing import Dict, Optional

from simulation.utils import DEFAULT_CONFIG, SimulationConfig, clamp, get_logger, risk_level_from_score

logger = get_logger(__name__)


def _normalized_density_score(density: float) -> float:
    """Map density (0+, typically 0-1.3) to a 0-100 sub-score."""
    # Density of 1.0 (at capacity) already scores highly; anything
    # beyond that saturates toward 100.
    return clamp(density * 100.0, 0.0, 100.0)


def _normalized_utilization_score(capacity_utilization: float) -> float:
    return clamp(capacity_utilization * 100.0, 0.0, 100.0)


def _normalized_flow_imbalance_score(flow_imbalance: float, capacity: float) -> float:
    """Large positive imbalance (filling fast) relative to capacity is risky."""
    if capacity <= 0:
        return 0.0
    relative = flow_imbalance / capacity
    # Only inflow-heavy imbalance raises risk; draining zones are safe.
    return clamp(relative * 300.0, 0.0, 100.0)


def _normalized_speed_score(avg_speed: float, base_speed: float = 1.4) -> float:
    """Slower average movement (crowd crush) increases risk."""
    if base_speed <= 0:
        return 0.0
    ratio = clamp(avg_speed / base_speed, 0.0, 1.0)
    return clamp((1.0 - ratio) * 100.0, 0.0, 100.0)


def _normalized_neighbor_pressure_score(neighbor_density: float) -> float:
    """High density in adjacent zones threatens to spill over."""
    return clamp(neighbor_density * 100.0, 0.0, 100.0)


def calculate_risk(zone_state: Dict, config: SimulationConfig = DEFAULT_CONFIG) -> Dict:
    """
    Compute a rule-based risk score and level for a single zone state.

    Args:
        zone_state: Dict with at least ``density``, ``capacity``,
            ``avg_speed``. Optionally: ``capacity_utilization``,
            ``flow_imbalance``, ``neighbor_zone_density``. Missing
            optional fields are derived or defaulted sensibly.
        config: Simulation config supplying risk weights and thresholds.

    Returns:
        ``{"risk_score": int, "risk_level": str}``
    """
    density = float(zone_state.get("density", 0.0))
    capacity = float(zone_state.get("capacity", 1.0))
    avg_speed = float(zone_state.get("avg_speed", 1.4))
    capacity_utilization = float(zone_state.get("capacity_utilization", density))
    flow_imbalance = float(zone_state.get("flow_imbalance", 0.0))
    neighbor_density = float(zone_state.get("neighbor_zone_density", density))

    density_score = _normalized_density_score(density)
    utilization_score = _normalized_utilization_score(capacity_utilization)
    imbalance_score = _normalized_flow_imbalance_score(flow_imbalance, capacity)
    speed_score = _normalized_speed_score(avg_speed)
    neighbor_score = _normalized_neighbor_pressure_score(neighbor_density)

    weighted_score = (
        density_score * config.weight_density
        + utilization_score * config.weight_capacity_utilization
        + imbalance_score * config.weight_flow_imbalance
        + speed_score * config.weight_speed
        + neighbor_score * config.weight_neighbor_pressure
    )
    risk_score = int(round(clamp(weighted_score, 0.0, 100.0)))
    risk_level = risk_level_from_score(risk_score, config)

    return {"risk_score": risk_score, "risk_level": risk_level.value}
