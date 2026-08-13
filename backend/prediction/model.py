"""
model.py

Thin wrapper classes around scikit-learn estimators, bundling the
model together with the feature column order and scaler it expects.
Keeping this bundling logic in one place avoids feature-order bugs
between training and inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import joblib
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.ensemble import GradientBoostingClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_COLUMNS


@dataclass
class CrowdModelBundle:
    """
    Bundles a fitted regressor (future density), a fitted classifier
    (bottleneck probability), the scaler used to normalize inputs, and
    the exact feature column order both models were trained on.
    """

    density_model: BaseEstimator
    bottleneck_model: BaseEstimator
    scaler: StandardScaler
    feature_columns: List[str] = field(default_factory=lambda: list(FEATURE_COLUMNS))

    def save(self, path: str) -> None:
        """Persist the entire bundle to disk with joblib."""
        joblib.dump(self, path)

    @staticmethod
    def load(path: str) -> "CrowdModelBundle":
        """Load a previously saved bundle from disk."""
        return joblib.load(path)


def build_density_model(random_state: int = 42) -> RandomForestRegressor:
    """Factory for the future-density regressor (Random Forest)."""
    return RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=random_state,
    )


def build_bottleneck_model(random_state: int = 42) -> GradientBoostingClassifier:
    """Factory for the bottleneck-probability classifier (Gradient Boosting)."""
    return GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        random_state=random_state,
    )
