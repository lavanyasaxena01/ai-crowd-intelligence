"""
utils.py

Shared constants, enums, and helper functions used across the
simulation package. Centralizing configuration here means no
magic numbers are scattered through the simulator or scenario
generator.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

def get_logger(name: str) -> logging.Logger:
    """
    Return a configured module-level logger.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance with a sensible default format.
        Safe to call multiple times; handlers are only attached once.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class ZoneType(str, Enum):
    """Functional classification of a zone inside a venue."""

    GATE = "gate"
    ENTRY = "entry"
    EXIT = "exit"
    CORRIDOR = "corridor"
    WAITING_AREA = "waiting_area"
    FOOD_COURT = "food_court"
    EVENT_ZONE = "event_zone"


class ScenarioType(str, Enum):
    """Supported synthetic scenario categories."""

    NORMAL_TRAFFIC = "normal_traffic"
    PEAK_TRAFFIC = "peak_traffic"
    GATE_CLOSURE = "gate_closure"
    EMERGENCY_EVACUATION = "emergency_evacuation"
    FOOD_COURT_RUSH = "food_court_rush"
    EVENT_ENDING = "event_ending"
    RANDOM_CONGESTION = "random_congestion"
    UNEVEN_DISTRIBUTION = "uneven_crowd_distribution"
    CORRIDOR_BLOCKAGE = "corridor_blockage"


class RiskLevel(str, Enum):
    """Discrete risk buckets derived from the continuous risk score."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SimulationConfig:
    """
    Central, immutable configuration object for a simulation run.

    All "magic numbers" referenced by the simulator live here so that
    behaviour can be tuned without touching simulation logic.
    """

    timestep_seconds: int = 10
    total_duration_seconds: int = 3600

    # Movement
    base_walk_speed_mps: float = 1.4          # comfortable walking speed
    min_speed_mps: float = 0.1                # near-standstill in a crush
    speed_density_exponent: float = 1.8       # how sharply speed collapses with density

    # Arrivals / departures
    base_arrival_rate: float = 6.0            # people per timestep at gates, normal traffic
    base_departure_rate: float = 5.0          # people per timestep leaving via exits
    peak_multiplier: float = 3.0
    surge_multiplier: float = 4.5             # event-ending surge

    # Random noise
    arrival_noise_std: float = 0.25           # relative std-dev applied to arrivals
    random_seed: Optional[int] = None

    # Risk engine weights (must sum to 1.0)
    weight_density: float = 0.35
    weight_capacity_utilization: float = 0.25
    weight_flow_imbalance: float = 0.15
    weight_speed: float = 0.15
    weight_neighbor_pressure: float = 0.10

    # Risk thresholds
    risk_low_max: int = 30
    risk_medium_max: int = 60
    risk_high_max: int = 80  # anything above -> CRITICAL


DEFAULT_CONFIG = SimulationConfig()


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive range [low, high]."""
    return max(low, min(high, value))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide two numbers, returning ``default`` instead of raising on /0."""
    if denominator == 0:
        return default
    return numerator / denominator


def set_global_seed(seed: Optional[int]) -> None:
    """Seed Python's ``random`` module for reproducible simulations."""
    if seed is not None:
        random.seed(seed)


def risk_level_from_score(score: float, config: SimulationConfig = DEFAULT_CONFIG) -> RiskLevel:
    """
    Map a numeric risk score (0-100) to a discrete :class:`RiskLevel`.

    Args:
        score: Risk score in the range [0, 100].
        config: Simulation configuration holding the threshold cutoffs.

    Returns:
        The corresponding :class:`RiskLevel`.
    """
    if score <= config.risk_low_max:
        return RiskLevel.LOW
    if score <= config.risk_medium_max:
        return RiskLevel.MEDIUM
    if score <= config.risk_high_max:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL
