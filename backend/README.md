# Crowd Simulation & AI Prediction Module

Part of the **Crowd Flow Optimiser** (Grand Prix Problem Statement 3).

This package simulates crowd movement, scores risk, and serves ML bottleneck predictions.
HTTP exposure lives in `api/app.py` (FastAPI). Vision lives in `vision/`.

## Run API

```bash
cd backend
venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

## Hugging Face

See root `HUGGINGFACE_SETUP.md`. Configure `backend/.env` with `HF_TOKEN`.


---

## 1. Project Structure

```
backend/
├── simulation/
│   ├── crowd_simulator.py   # Core discrete-time simulation engine
│   ├── scenario_generator.py# Venue templates + dataset generation
│   ├── agent.py              # Individual simulated person
│   └── utils.py               # Config, enums, logging, helpers
│
├── prediction/
│   ├── features.py           # Reusable feature engineering pipeline
│   ├── risk_engine.py        # Rule-based 0-100 risk scoring
│   ├── train.py               # Training pipeline (labels, CV, metrics)
│   ├── predictor.py          # Public functions for backend integration
│   └── model.py               # Model bundle wrapper + factories
│
├── data/
│   ├── generated/            # Synthetic CSV datasets
│   └── models/                 # Saved joblib model bundles
│
├── tests/
│   ├── test_simulation.py
│   └── test_prediction.py
│
├── requirements.txt
└── README.md
```

---

## 2. Installation

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Requires **Python 3.11+**.

---

## 3. Usage Guide

### 3.1 Run a simulation

```python
from simulation.scenario_generator import build_stadium
from simulation.utils import SimulationConfig

config = SimulationConfig(timestep_seconds=10, total_duration_seconds=1800, random_seed=42)
sim = build_stadium(config)
records = sim.run(scenario="peak_traffic")   # list[dict] — one dict per zone per timestep
```

Available venue templates: `build_stadium`, `build_airport`,
`build_metro_station`, `build_concert_venue`, `build_exhibition_hall`
(all in `simulation.scenario_generator`).

Supported scenario names: `normal_traffic`, `peak_traffic`, `gate_closure`,
`emergency_evacuation`, `food_court_rush`, `event_ending`,
`random_congestion`, `uneven_crowd_distribution`, `corridor_blockage`.

### 3.2 Generate a large synthetic dataset

```python
from simulation.scenario_generator import ScenarioGenerator

gen = ScenarioGenerator(output_dir="data/generated")
df = gen.generate_dataset(runs_per_combo=20, duration_seconds=1800)
# Saved to data/generated/generated_dataset.csv
```

Every (venue × scenario × run) combination uses a distinct random seed, so
`runs_per_combo=20` across 5 venues and 9 scenarios yields 900 independent
simulation runs — easily tens of thousands of rows.

### 3.3 Train the ML models

```bash
python -m prediction.train --data data/generated/generated_dataset.csv \
                            --output data/models/model.joblib \
                            --horizon 3 --cv-folds 5
```

This engineers features, builds `future_density` / `bottleneck` labels via a
look-ahead window, trains a `RandomForestRegressor` (density) and a
`GradientBoostingClassifier` (bottleneck) with 5-fold cross-validation, and
prints MAE / RMSE / R² and Accuracy / F1 / ROC-AUC. The fitted bundle
(models + scaler + feature order) is saved with `joblib`.

### 3.4 Use in a Flask/FastAPI backend

```python
from prediction.predictor import calculate_risk, predict_density, predict_bottleneck, load_model

# Warm the model cache at app startup (optional but recommended)
load_model("data/models/model.joblib")

@app.route("/api/risk", methods=["POST"])
def risk():
    return calculate_risk(request.json)   # rule-based, no model needed

@app.route("/api/predict", methods=["POST"])
def predict():
    return predict_bottleneck(request.json)  # ML-based, needs a trained model
```

All four functions accept/return plain, JSON-serializable dicts.

---

## 4. Function Documentation

### `calculate_risk(zone_state: dict) -> dict`
Rule-based congestion score, no ML model required.
Input keys used: `density`, `capacity`, `avg_speed`, and optionally
`capacity_utilization`, `flow_imbalance`, `neighbor_zone_density`.
Returns `{"risk_score": int, "risk_level": str}`.

### `predict_density(features: dict, model_path=...) -> dict`
ML-based future density prediction. `features` should contain the
engineered feature columns (see `prediction.features.FEATURE_COLUMNS`);
missing ones default to 0.0. Returns `{"predicted_density": float}`.

### `predict_bottleneck(zone_state: dict, model_path=...) -> dict`
Combines the rule-based risk score with ML-predicted density and
bottleneck probability. Returns:
```json
{
  "zone": "corridor_B",
  "risk_score": 92,
  "risk_level": "HIGH",
  "predicted_density": 1.05,
  "bottleneck_probability": 0.87,
  "time_to_bottleneck": 2.7
}
```

### `load_model(path=..., force_reload=False) -> CrowdModelBundle`
Loads and thread-safely caches the trained model bundle. Raises
`FileNotFoundError` if `train.py` hasn't been run yet.

---

## 5. Feature Engineering Reference

`prediction.features.engineer_features(df)` derives, per zone/timestamp:

| Feature                        | Meaning                                            |
|--------------------------------|-----------------------------------------------------|
| `capacity_utilization`         | people_count / capacity                             |
| `flow_imbalance`                | inflow − outflow                                     |
| `previous_density`              | density at the prior timestep (lag-1)               |
| `rolling_avg_density`           | rolling mean density (default window = 3)           |
| `neighbor_zone_density`         | mean density of topologically adjacent zones        |
| `historical_congestion_trend`   | density − previous_density                          |

---

## 6. Risk Engine Reference

Weighted sum of five normalized (0-100) sub-scores — density, capacity
utilization, flow imbalance, inverse speed, and neighbor pressure — combined
per `SimulationConfig` weights (defaults: 0.35 / 0.25 / 0.15 / 0.15 / 0.10).

| Score Range | Risk Level |
|-------------|------------|
| 0 – 30      | LOW        |
| 31 – 60     | MEDIUM     |
| 61 – 80     | HIGH       |
| 81 – 100    | CRITICAL   |

---

## 7. Testing

```bash
pytest tests/ -v
```

Covers venue construction, simulation record shape, scenario differentiation
(e.g. peak traffic vs. normal, gate closure reducing arrivals), feature
engineering correctness, and risk-engine monotonicity/thresholds.

---

## 8. Design Notes

- **No hardcoded values**: all tunables (speeds, rates, weights, thresholds)
  live in `simulation.utils.SimulationConfig`.
- **Deterministic pathfinding**: agents route via BFS over the zone graph
  (no external graph dependency required); `networkx` is used only for the
  optional `to_networkx()` export.
- **Congestion-aware movement**: agents slow down and may wait when a target
  zone is above ~115% capacity, and the average-speed metric collapses
  smoothly as density rises, so crowd-crush effects show up organically in
  the generated data rather than being scripted.
- **Model bundle**: `CrowdModelBundle` stores the density regressor, the
  bottleneck classifier, the fitted `StandardScaler`, and the exact feature
  column order together, so training/inference can never drift out of sync.
