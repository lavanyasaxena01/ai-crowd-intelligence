"""
predictor.py

The public, backend-facing API of the prediction package. Exposes
exactly the functions the rest of the team needs to import:

    calculate_risk(zone_state)
    predict_density(features)
    predict_bottleneck(zone_state)
    load_model()

All functions accept and return plain Python dicts (JSON-serializable)
so they drop straight into a Flask/FastAPI route handler.
"""

from __future__ import annotations

import os
import threading
from typing import Dict, Optional

import numpy as np
import pandas as pd

from simulation.utils import get_logger
from .features import FEATURE_COLUMNS
from .model import CrowdModelBundle
from .risk_engine import calculate_risk as _calculate_risk

logger = get_logger(__name__)

DEFAULT_MODEL_PATH = os.path.join("data", "models", "model.joblib")

_model_lock = threading.Lock()
_cached_bundle: Optional[CrowdModelBundle] = None
_cached_path: Optional[str] = None


def load_model(path: str = DEFAULT_MODEL_PATH, force_reload: bool = False) -> CrowdModelBundle:
    """
    Load (and cache) the trained model bundle.

    Args:
        path: Path to the joblib file produced by ``train.py``.
        force_reload: If True, bypass the cache and reload from disk.

    Returns:
        The loaded :class:`CrowdModelBundle`.

    Raises:
        FileNotFoundError: If no model has been trained/saved yet at ``path``.
    """
    global _cached_bundle, _cached_path

    with _model_lock:
        if _cached_bundle is not None and _cached_path == path and not force_reload:
            return _cached_bundle

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No trained model found at '{path}'. Run prediction/train.py first."
            )

        logger.info("Loading model bundle from %s", path)
        _cached_bundle = CrowdModelBundle.load(path)
        _cached_path = path
        return _cached_bundle


def _features_to_frame(features: Dict) -> pd.DataFrame:
    """Coerce a feature dict into a single-row DataFrame with the correct
    column order, filling any missing engineered features with 0.0."""
    row = {col: float(features.get(col, 0.0)) for col in FEATURE_COLUMNS}
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def predict_density(features: Dict, model_path: str = DEFAULT_MODEL_PATH) -> Dict:
    """
    Predict future crowd density for a single zone state.

    Args:
        features: Dict containing at least the engineered feature
            columns (see ``prediction.features.FEATURE_COLUMNS``).
            Missing features default to 0.0.
        model_path: Path to the trained model bundle.

    Returns:
        ``{"predicted_density": float}``
    """
    bundle = load_model(model_path)
    X = _features_to_frame(features)
    X_scaled = bundle.scaler.transform(X)
    predicted = float(bundle.density_model.predict(X_scaled)[0])
    return {"predicted_density": round(predicted, 4)}


def predict_bottleneck(zone_state: Dict, model_path: str = DEFAULT_MODEL_PATH) -> Dict:
    """
    Full prediction for a zone: risk score/level (rule-based), plus
    ML-predicted future density, bottleneck probability, and an
    estimated time-to-bottleneck (in timesteps).

    Args:
        zone_state: Dict with raw + engineered fields for the zone,
            e.g. density, capacity, avg_speed, inflow, outflow,
            capacity_utilization, flow_imbalance, previous_density,
            rolling_avg_density, neighbor_zone_density,
            historical_congestion_trend, and ``zone`` (name).
        model_path: Path to the trained model bundle.

    Returns:
        ``{"zone": str, "risk_score": int, "risk_level": str,
           "predicted_density": float, "time_to_bottleneck": float}``
    """
    bundle = load_model(model_path)
    X = _features_to_frame(zone_state)
    X_scaled = bundle.scaler.transform(X)

    predicted_density = float(bundle.density_model.predict(X_scaled)[0])
    bottleneck_proba = float(bundle.bottleneck_model.predict_proba(X_scaled)[0][1])

    risk = _calculate_risk(zone_state)

    # Estimate time-to-bottleneck: higher probability + higher predicted
    # density imply an imminent bottleneck; this is a simple monotonic
    # heuristic layered on top of the classifier's probability, expressed
    # in simulation timesteps.
    # Capped at 5.0 timesteps (the training horizon) so the value always
    # stays JSON-serializable rather than emitting Infinity/NaN.
    time_to_bottleneck = round(max(0.5, (1.0 - bottleneck_proba) * 5.0), 2)

    result = {
        "zone": zone_state.get("zone", "unknown"),
        "risk_score": risk["risk_score"],
        "risk_level": risk["risk_level"],
        "predicted_density": round(predicted_density, 4),
        "bottleneck_probability": round(bottleneck_proba, 4),
        "time_to_bottleneck": time_to_bottleneck,
    }
    return result


def calculate_risk(zone_state: Dict) -> Dict:
    """Re-exported rule-based risk calculation (no model required).

    See :func:`prediction.risk_engine.calculate_risk` for details.
    """
    return _calculate_risk(zone_state)
