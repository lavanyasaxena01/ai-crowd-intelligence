"""
train.py

End-to-end training pipeline:

1. Load a generated dataset (CSV).
2. Engineer features.
3. Build supervised labels:
   - future_density        (regression target)
   - bottleneck            (binary classification target)
   - time_to_bottleneck    (derived, reported but not directly modeled)
4. Train/test split + cross-validation.
5. Fit RandomForestRegressor (density) and GradientBoostingClassifier
   (bottleneck).
6. Report MAE / RMSE / R^2 (regression) and standard classification
   metrics.
7. Persist the fitted bundle with joblib.

Run directly:
    python -m prediction.train --data data/generated/generated_dataset.csv
"""

from __future__ import annotations

import argparse
import os
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

from simulation.utils import get_logger
from .features import FEATURE_COLUMNS, engineer_features
from .model import CrowdModelBundle, build_bottleneck_model, build_density_model

logger = get_logger(__name__)

DEFAULT_BOTTLENECK_THRESHOLD = 1.0  # density >= capacity
DEFAULT_HORIZON_STEPS = 3           # look-ahead steps for "future" labels


def build_labels(
    df: pd.DataFrame,
    horizon: int = DEFAULT_HORIZON_STEPS,
    bottleneck_threshold: float = DEFAULT_BOTTLENECK_THRESHOLD,
    group_cols: Tuple[str, ...] = ("venue", "scenario", "run_id", "zone"),
) -> pd.DataFrame:
    """
    Add supervised-learning targets to an engineered feature frame.

    Args:
        df: Output of :func:`engineer_features`, still containing
            venue/scenario/run_id/zone grouping columns.
        horizon: Number of future timesteps to look ahead for the
            density/bottleneck labels.
        bottleneck_threshold: Density at/above which a zone is
            considered to have hit a bottleneck.
        group_cols: Columns identifying an independent time series
            (a single zone within a single simulation run).

    Returns:
        DataFrame with added columns: ``future_density``,
        ``bottleneck``, ``time_to_bottleneck``. Rows too close to the
        end of their series to have a full look-ahead window are
        dropped.
    """
    present_group_cols = [c for c in group_cols if c in df.columns]
    if not present_group_cols:
        raise ValueError(f"None of the expected grouping columns {group_cols} found in DataFrame.")

    df = df.sort_values(present_group_cols + ["timestamp"]).reset_index(drop=True)

    def _label_group(group: pd.DataFrame) -> pd.DataFrame:
        density = group["density"].to_numpy()
        n = len(density)
        future_density = np.full(n, np.nan)
        bottleneck = np.zeros(n, dtype=int)
        time_to_bottleneck = np.full(n, float(horizon))

        for i in range(n):
            end = min(i + horizon, n - 1)
            if end == i:
                continue
            window = density[i + 1 : end + 1]
            future_density[i] = window[-1] if len(window) else np.nan
            hits = np.where(window >= bottleneck_threshold)[0]
            if len(hits) > 0:
                bottleneck[i] = 1
                time_to_bottleneck[i] = float(hits[0] + 1)
        group = group.copy()
        group["future_density"] = future_density
        group["bottleneck"] = bottleneck
        group["time_to_bottleneck"] = time_to_bottleneck
        return group

    labeled = df.groupby(present_group_cols, group_keys=False).apply(_label_group)
    labeled = labeled.dropna(subset=["future_density"]).reset_index(drop=True)
    logger.info("Built labels for %d rows (dropped rows too close to series end).", len(labeled))
    return labeled


def train_models(
    data_path: str,
    model_output_path: str = "data/models/model.joblib",
    horizon: int = DEFAULT_HORIZON_STEPS,
    bottleneck_threshold: float = DEFAULT_BOTTLENECK_THRESHOLD,
    test_size: float = 0.2,
    cv_folds: int = 5,
    random_state: int = 42,
) -> CrowdModelBundle:
    """
    Full training pipeline: load data, engineer features, build labels,
    train both models, evaluate, and save the bundle.

    Args:
        data_path: Path to a CSV produced by ``ScenarioGenerator``.
        model_output_path: Where to save the joblib model bundle.
        horizon: Look-ahead steps for future_density / bottleneck labels.
        bottleneck_threshold: Density threshold defining a bottleneck.
        test_size: Fraction of data held out for testing.
        cv_folds: Number of cross-validation folds on the training set.
        random_state: Seed for reproducibility.

    Returns:
        The fitted :class:`CrowdModelBundle`.
    """
    logger.info("Loading dataset from %s", data_path)
    raw = pd.read_csv(data_path)

    engineered = engineer_features(raw)
    # Re-attach grouping columns dropped by engineer_features's own indexing.
    for col in ("venue", "scenario", "run_id"):
        if col in raw.columns and col not in engineered.columns:
            engineered[col] = raw[col]

    labeled = build_labels(engineered, horizon=horizon, bottleneck_threshold=bottleneck_threshold)

    X = labeled[FEATURE_COLUMNS].fillna(0.0)
    y_density = labeled["future_density"]
    y_bottleneck = labeled["bottleneck"]

    X_train, X_test, yd_train, yd_test, yb_train, yb_test = train_test_split(
        X, y_density, y_bottleneck, test_size=test_size, random_state=random_state, stratify=y_bottleneck
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # --- Density regressor ---
    density_model = build_density_model(random_state=random_state)
    cv_scores = cross_val_score(density_model, X_train_scaled, yd_train, cv=cv_folds, scoring="r2")
    logger.info("Density model CV R^2: mean=%.4f std=%.4f", cv_scores.mean(), cv_scores.std())

    density_model.fit(X_train_scaled, yd_train)
    yd_pred = density_model.predict(X_test_scaled)

    mae = mean_absolute_error(yd_test, yd_pred)
    # np.sqrt(mse) used instead of the `squared=False` kwarg for
    # compatibility across scikit-learn versions.
    rmse = float(np.sqrt(mean_squared_error(yd_test, yd_pred)))
    r2 = r2_score(yd_test, yd_pred)
    logger.info("Density model test metrics -> MAE=%.4f RMSE=%.4f R2=%.4f", mae, rmse, r2)

    # --- Bottleneck classifier ---
    bottleneck_model = build_bottleneck_model(random_state=random_state)
    cv_scores_clf = cross_val_score(bottleneck_model, X_train_scaled, yb_train, cv=cv_folds, scoring="f1")
    logger.info("Bottleneck model CV F1: mean=%.4f std=%.4f", cv_scores_clf.mean(), cv_scores_clf.std())

    bottleneck_model.fit(X_train_scaled, yb_train)
    yb_pred = bottleneck_model.predict(X_test_scaled)
    yb_proba = bottleneck_model.predict_proba(X_test_scaled)[:, 1]

    acc = accuracy_score(yb_test, yb_pred)
    f1 = f1_score(yb_test, yb_pred, zero_division=0)
    try:
        auc = roc_auc_score(yb_test, yb_proba)
    except ValueError:
        auc = float("nan")  # only one class present in test split
    logger.info("Bottleneck model test metrics -> Accuracy=%.4f F1=%.4f ROC-AUC=%.4f", acc, f1, auc)

    bundle = CrowdModelBundle(
        density_model=density_model,
        bottleneck_model=bottleneck_model,
        scaler=scaler,
        feature_columns=list(FEATURE_COLUMNS),
    )

    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    bundle.save(model_output_path)
    logger.info("Saved model bundle to %s", model_output_path)

    return bundle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train crowd density / bottleneck prediction models.")
    parser.add_argument("--data", type=str, default="data/generated/generated_dataset.csv")
    parser.add_argument("--output", type=str, default="data/models/model.joblib")
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_STEPS)
    parser.add_argument("--threshold", type=float, default=DEFAULT_BOTTLENECK_THRESHOLD)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--cv-folds", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train_models(
        data_path=args.data,
        model_output_path=args.output,
        horizon=args.horizon,
        bottleneck_threshold=args.threshold,
        test_size=args.test_size,
        cv_folds=args.cv_folds,
    )
