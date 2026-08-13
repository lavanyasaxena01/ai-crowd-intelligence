"""Tests for feature engineering, risk engine, and predictor functions."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from prediction.features import engineer_features, FEATURE_COLUMNS
from prediction.risk_engine import calculate_risk


def _sample_df() -> pd.DataFrame:
    rows = []
    for t in range(5):
        rows.append(
            {
                "timestamp": t * 10,
                "zone": "corridor_B",
                "people_count": 500 + t * 50,
                "capacity": 800,
                "inflow": 60,
                "outflow": 10,
                "density": (500 + t * 50) / 800,
                "avg_speed": max(0.2, 1.4 - t * 0.2),
            }
        )
    return pd.DataFrame(rows)


def test_engineer_features_adds_expected_columns():
    df = _sample_df()
    out = engineer_features(df)
    for col in FEATURE_COLUMNS:
        assert col in out.columns
    assert len(out) == len(df)


def test_flow_imbalance_calculation():
    df = _sample_df()
    out = engineer_features(df)
    assert (out["flow_imbalance"] == out["inflow"] - out["outflow"]).all()


def test_risk_engine_low_density_gives_low_risk():
    state = {
        "density": 0.1,
        "capacity": 800,
        "avg_speed": 1.4,
        "capacity_utilization": 0.1,
        "flow_imbalance": 0,
        "neighbor_zone_density": 0.1,
    }
    result = calculate_risk(state)
    assert result["risk_level"] == "LOW"
    assert 0 <= result["risk_score"] <= 30


def test_risk_engine_high_density_gives_high_risk():
    state = {
        "density": 1.1,
        "capacity": 800,
        "avg_speed": 0.3,
        "capacity_utilization": 1.1,
        "flow_imbalance": 150,
        "neighbor_zone_density": 0.95,
    }
    result = calculate_risk(state)
    assert result["risk_score"] > 60
    assert result["risk_level"] in ("HIGH", "CRITICAL")


def test_risk_score_monotonic_with_density():
    low = calculate_risk({"density": 0.2, "capacity": 500, "avg_speed": 1.4})
    high = calculate_risk({"density": 1.2, "capacity": 500, "avg_speed": 0.3})
    assert high["risk_score"] > low["risk_score"]
