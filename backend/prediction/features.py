"""
features.py

Reusable feature engineering pipeline. Takes raw simulation/dataset
records (timestamp, zone, people_count, capacity, inflow, outflow,
density, avg_speed) and derives the ML-ready feature set:

- capacity_utilization
- flow_imbalance
- previous_density (lagged)
- rolling_avg_density
- neighbor_zone_density
- historical_congestion_trend

The pipeline is stateless with respect to any particular model: it
can be reused identically at training time and at inference time.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from simulation.utils import get_logger, safe_divide

logger = get_logger(__name__)


REQUIRED_COLUMNS = [
    "timestamp",
    "zone",
    "people_count",
    "capacity",
    "inflow",
    "outflow",
    "density",
    "avg_speed",
]


def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input DataFrame is missing required columns: {missing}")


def _neighbor_density_map(df: pd.DataFrame, neighbor_lookup: Optional[Dict[str, List[str]]]) -> pd.Series:
    """
    Compute, for each row, the mean density of neighboring zones at the
    same timestamp. Falls back to the zone's own density if no
    neighbor topology is supplied.
    """
    if not neighbor_lookup:
        return df["density"]

    # Build a (timestamp, zone) -> density lookup for fast access.
    density_lookup = df.set_index(["timestamp", "zone"])["density"].to_dict()

    def _lookup(row) -> float:
        neighbors = neighbor_lookup.get(row["zone"], [])
        if not neighbors:
            return row["density"]
        values = [
            density_lookup.get((row["timestamp"], n))
            for n in neighbors
            if density_lookup.get((row["timestamp"], n)) is not None
        ]
        return float(np.mean(values)) if values else row["density"]

    return df.apply(_lookup, axis=1)


def engineer_features(
    df: pd.DataFrame,
    neighbor_lookup: Optional[Dict[str, List[str]]] = None,
    rolling_window: int = 3,
) -> pd.DataFrame:
    """
    Derive the full ML feature set from raw crowd-state records.

    Args:
        df: Raw records with columns matching ``REQUIRED_COLUMNS``.
            Should include multiple timestamps per zone for the
            lag/rolling features to be meaningful (a single-timestep
            snapshot will produce zero-filled lag features).
        neighbor_lookup: Optional mapping of zone_id -> list of
            neighboring zone_ids, used for the ``neighbor_zone_density``
            feature. If omitted, the zone's own density is used.
        rolling_window: Window size (in timesteps) for the rolling
            average density feature.

    Returns:
        A new DataFrame with the original columns plus:
        ``capacity_utilization``, ``flow_imbalance``,
        ``previous_density``, ``rolling_avg_density``,
        ``neighbor_zone_density``, ``historical_congestion_trend``.
    """
    _validate_columns(df)
    out = df.copy()
    out = out.sort_values(["zone", "timestamp"]).reset_index(drop=True)

    # Capacity utilization: identical to density when capacity basis matches,
    # kept as a distinct, explicitly-named feature per spec.
    out["capacity_utilization"] = out.apply(
        lambda r: safe_divide(r["people_count"], r["capacity"]), axis=1
    )

    # Flow imbalance: positive means the zone is filling up, negative draining.
    out["flow_imbalance"] = out["inflow"] - out["outflow"]

    # Per-zone lag and rolling features.
    grouped = out.groupby("zone", group_keys=False)
    out["previous_density"] = grouped["density"].shift(1).fillna(out["density"])
    out["rolling_avg_density"] = (
        grouped["density"]
        .apply(lambda s: s.rolling(window=rolling_window, min_periods=1).mean())
        .reset_index(drop=True)
    )

    # Historical congestion trend: slope of density over the rolling window,
    # i.e. is congestion getting better or worse.
    out["historical_congestion_trend"] = out["density"] - out["previous_density"]

    # Neighbor zone density.
    out["neighbor_zone_density"] = _neighbor_density_map(out, neighbor_lookup)

    logger.info("Engineered features for %d rows across %d zones.", len(out), out["zone"].nunique())
    return out


FEATURE_COLUMNS = [
    "density",
    "capacity_utilization",
    "inflow",
    "outflow",
    "flow_imbalance",
    "avg_speed",
    "previous_density",
    "rolling_avg_density",
    "neighbor_zone_density",
    "historical_congestion_trend",
]
