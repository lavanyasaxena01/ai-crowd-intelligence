"""
Crowd Simulation package.

Exposes the core simulation primitives used to generate synthetic
crowd-movement data for the AI-Powered Crowd Intelligence System.
"""

from .agent import Agent
from .crowd_simulator import CrowdSimulator, Zone
from .scenario_generator import ScenarioGenerator

__all__ = [
    "Agent",
    "CrowdSimulator",
    "Zone",
    "ScenarioGenerator",
]
