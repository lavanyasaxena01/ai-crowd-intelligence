# Crowd Intelligence API Contract

Base URL: `http://localhost:8000`

Thin FastAPI wrapper around existing `simulation` / `prediction` packages.

---

## GET /api/health

**Response:**
```json
{
  "status": "ok",
  "model_available": true,
  "model_loaded": true,
  "model_path": ".../data/models/model.joblib",
  "model_error": null,
  "simulator_ready": true,
  "venues": ["stadium", "airport", "..."],
  "scenarios": ["normal_traffic", "peak_traffic", "..."],
  "timestamp": "2026-08-11T15:00:00+00:00"
}
```

---

## GET /api/venues

```json
{ "venues": [{ "id": "stadium", "name": "Stadium" }] }
```

## GET /api/scenarios

```json
{ "scenarios": [{ "id": "peak_traffic", "name": "Peak Traffic" }] }
```

## GET /api/venues/{venue_id}/graph

Returns real simulator topology: nodes, edges, gates, exits, food_courts, event_zones.

---

## POST /api/simulation

**Request:**
```json
{
  "venue": "stadium",
  "scenario": "peak_traffic",
  "duration_seconds": 600,
  "random_seed": 42,
  "arrival_rate": null,
  "expected_crowd_size": 30000,
  "event_schedule": {
    "start_time": "18:00",
    "peak_window_minutes": 30,
    "event_duration_minutes": 120
  }
}
```

`expected_crowd_size` and `event_schedule` are mapped onto the existing simulator's
`base_arrival_rate` (no duplicate simulation math). Explicit `arrival_rate` overrides
the crowd-size derivation (schedule still applies mild intensity).

---

## GET /api/vision/status

```json
{ "configured": false, "model": "facebook/detr-resnet-50", "token_present": false, "message": "..." }
```

## POST /api/vision/analyze

Multipart form field: `file` (image/*)

**Response:**
```json
{
  "status": "ok",
  "source": "huggingface",
  "model": "facebook/detr-resnet-50",
  "people_detected": 12,
  "detections": [{ "label": "person", "score": 0.98, "box": { "xmin": 1, "ymin": 2, "xmax": 3, "ymax": 4 } }],
  "label_counts": { "person": 12 },
  "observation": "Detected 12 person(s) via Hugging Face model ..."
}
```

Requires `HF_TOKEN` in `backend/.env`. Never returns fabricated detections.

---

## POST /api/routing

**Request:**
```json
{ "venue": "stadium", "source": "gate_1", "target": "bowl_lower", "max_alternates": 3 }
```

**Success:**
```json
{
  "status": "ok",
  "source": "gate_1",
  "destination": "bowl_lower",
  "recommended": {
    "path": ["gate_1", "concourse_north", "food_court_1", "concourse_south", "bowl_lower"],
    "hops": 4,
    "distance_m": 380,
    "travel_time_s": 42,
    "risk_score": 45,
    "risk_level": "MEDIUM"
  },
  "routes": [],
  "message": null
}
```

**No route:**
```json
{
  "status": "no_route",
  "recommended": null,
  "routes": [],
  "message": "NO SAFE ROUTE FOUND"
}
```

A path is valid only if `path[-1] == target` (or `source == target`).

---

## GET /api/intervention/recommend

Requires a prior simulation.

```json
{
  "status": "proposed",
  "detected_bottleneck": "food_court_1",
  "current_risk_score": 72,
  "current_risk_level": "HIGH",
  "reason": "Reduces inflow pressure toward predicted bottleneck ...",
  "recommended_action": {
    "type": "REDIRECT",
    "action": "REDIRECT",
    "source": "gate_1",
    "target": "gate_2",
    "percentage": 20,
    "description": "Redirect traffic gate_1 -> gate_2"
  }
}
```

Statuses: `proposed` | `no_alternative` | `unavailable`

---

## POST /api/intervention/simulate

**Request:** `{ "redirect_percentage": 25 }` (optional override)

Evaluates candidate percentages. **Accepts only if overall risk decreases.**

**Applied:**
```json
{
  "status": "applied",
  "beneficial": true,
  "message": "Intervention improves crowd distribution",
  "risk_before": 72,
  "risk_after": 54,
  "percentage": 25,
  "source": "gate_1",
  "target": "gate_2",
  "before": { "risk_score": 72, "stats": {} },
  "after": { "risk_score": 54, "zones": [], "forecast": [] },
  "change": { "risk_delta": -18, "risk_reduction_pct": 25.0 }
}
```

**Rejected:**
```json
{
  "status": "rejected",
  "beneficial": false,
  "message": "No beneficial intervention found",
  "before": { "risk_score": 20 },
  "after": null
}
```

Baseline simulation state is restored when rejected.

---

## POST /api/what-if

**Request:** `{ "test_arrival_rate": 24.0 }`

Exploratory — does **not** overwrite the operational snapshot.

```json
{
  "status": "ok",
  "baseline": { "risk_score": 40, "density": 0.3, "arrival_rate": 12 },
  "current": { "risk_score": 40, "density": 0.3 },
  "what_if": { "risk_score": 70, "density": 0.55 },
  "comparison": { "risk_change": 30, "density_change": 0.25, "eta_change": -1.2 },
  "change": { "risk_delta": 30, "density_delta": 0.25, "eta_delta": -1.2 }
}
```
