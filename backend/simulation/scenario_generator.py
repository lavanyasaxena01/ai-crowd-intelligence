"""
scenario_generator.py

Builds ready-made venue graphs (stadium, airport, metro station,
concert venue, exhibition hall) and runs the ``CrowdSimulator`` across
many scenario/venue/seed combinations to produce large synthetic
datasets, saved as CSV files under ``data/generated/``.
"""

from __future__ import annotations

import os
import random
from dataclasses import replace
from typing import Dict, List, Optional

import pandas as pd

from .crowd_simulator import CrowdSimulator, Zone
from .utils import DEFAULT_CONFIG, ScenarioType, SimulationConfig, ZoneType, get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Venue templates
# --------------------------------------------------------------------------- #

def build_stadium(config: SimulationConfig = DEFAULT_CONFIG) -> CrowdSimulator:
    """Construct a stadium-style venue: gates -> concourse -> seating bowl."""
    sim = CrowdSimulator(config)
    zones = [
        Zone("gate_1", ZoneType.GATE, capacity=300, area_sqm=80),
        Zone("gate_2", ZoneType.GATE, capacity=300, area_sqm=80),
        Zone("gate_3", ZoneType.GATE, capacity=300, area_sqm=80),
        Zone("concourse_north", ZoneType.CORRIDOR, capacity=800, area_sqm=400),
        Zone("concourse_south", ZoneType.CORRIDOR, capacity=800, area_sqm=400),
        Zone("food_court_1", ZoneType.FOOD_COURT, capacity=250, area_sqm=200),
        Zone("bowl_lower", ZoneType.EVENT_ZONE, capacity=5000, area_sqm=2500),
        Zone("bowl_upper", ZoneType.EVENT_ZONE, capacity=4000, area_sqm=2200),
        Zone("exit_1", ZoneType.EXIT, capacity=400, area_sqm=100),
        Zone("exit_2", ZoneType.EXIT, capacity=400, area_sqm=100),
    ]
    for z in zones:
        sim.add_zone(z)

    sim.connect("gate_1", "concourse_north")
    sim.connect("gate_2", "concourse_north")
    sim.connect("gate_3", "concourse_south")
    sim.connect("concourse_north", "food_court_1")
    sim.connect("concourse_north", "bowl_upper")
    sim.connect("concourse_south", "bowl_lower")
    sim.connect("concourse_south", "food_court_1")
    sim.connect("bowl_lower", "exit_1")
    sim.connect("bowl_upper", "exit_2")
    sim.connect("concourse_north", "exit_2")
    sim.connect("concourse_south", "exit_1")
    return sim


def build_airport(config: SimulationConfig = DEFAULT_CONFIG) -> CrowdSimulator:
    """Construct an airport terminal: entry -> security -> corridors -> gates."""
    sim = CrowdSimulator(config)
    zones = [
        Zone("entry_1", ZoneType.GATE, capacity=200, area_sqm=100),
        Zone("security", ZoneType.WAITING_AREA, capacity=150, area_sqm=150),
        Zone("corridor_A", ZoneType.CORRIDOR, capacity=400, area_sqm=300),
        Zone("corridor_B", ZoneType.CORRIDOR, capacity=400, area_sqm=300),
        Zone("food_court_1", ZoneType.FOOD_COURT, capacity=200, area_sqm=180),
        Zone("boarding_gate_1", ZoneType.EVENT_ZONE, capacity=180, area_sqm=150),
        Zone("boarding_gate_2", ZoneType.EVENT_ZONE, capacity=180, area_sqm=150),
        Zone("exit_1", ZoneType.EXIT, capacity=300, area_sqm=100),
    ]
    for z in zones:
        sim.add_zone(z)

    sim.connect("entry_1", "security")
    sim.connect("security", "corridor_A")
    sim.connect("corridor_A", "corridor_B")
    sim.connect("corridor_A", "food_court_1")
    sim.connect("corridor_B", "boarding_gate_1")
    sim.connect("corridor_B", "boarding_gate_2")
    sim.connect("boarding_gate_1", "exit_1")
    sim.connect("boarding_gate_2", "exit_1")
    return sim


def build_metro_station(config: SimulationConfig = DEFAULT_CONFIG) -> CrowdSimulator:
    """Construct a metro station: street entries -> concourse -> platforms."""
    sim = CrowdSimulator(config)
    zones = [
        Zone("gate_1", ZoneType.GATE, capacity=250, area_sqm=60),
        Zone("gate_2", ZoneType.GATE, capacity=250, area_sqm=60),
        Zone("concourse", ZoneType.CORRIDOR, capacity=600, area_sqm=350),
        Zone("platform_1", ZoneType.WAITING_AREA, capacity=350, area_sqm=200),
        Zone("platform_2", ZoneType.WAITING_AREA, capacity=350, area_sqm=200),
        Zone("exit_1", ZoneType.EXIT, capacity=300, area_sqm=70),
    ]
    for z in zones:
        sim.add_zone(z)

    sim.connect("gate_1", "concourse")
    sim.connect("gate_2", "concourse")
    sim.connect("concourse", "platform_1")
    sim.connect("concourse", "platform_2")
    sim.connect("platform_1", "exit_1")
    sim.connect("platform_2", "exit_1")
    return sim


def build_concert_venue(config: SimulationConfig = DEFAULT_CONFIG) -> CrowdSimulator:
    """Construct a concert venue: entries -> general admission floor -> exits."""
    sim = CrowdSimulator(config)
    zones = [
        Zone("gate_1", ZoneType.GATE, capacity=400, area_sqm=90),
        Zone("gate_2", ZoneType.GATE, capacity=400, area_sqm=90),
        Zone("lobby", ZoneType.CORRIDOR, capacity=700, area_sqm=350),
        Zone("bar_area", ZoneType.FOOD_COURT, capacity=200, area_sqm=150),
        Zone("main_floor", ZoneType.EVENT_ZONE, capacity=3000, area_sqm=1500),
        Zone("exit_1", ZoneType.EXIT, capacity=500, area_sqm=120),
        Zone("exit_2", ZoneType.EXIT, capacity=500, area_sqm=120),
    ]
    for z in zones:
        sim.add_zone(z)

    sim.connect("gate_1", "lobby")
    sim.connect("gate_2", "lobby")
    sim.connect("lobby", "bar_area")
    sim.connect("lobby", "main_floor")
    sim.connect("main_floor", "exit_1")
    sim.connect("main_floor", "exit_2")
    sim.connect("lobby", "exit_1")
    return sim


def build_exhibition_hall(config: SimulationConfig = DEFAULT_CONFIG) -> CrowdSimulator:
    """Construct an exhibition hall: entries -> aisles -> booths -> exits."""
    sim = CrowdSimulator(config)
    zones = [
        Zone("gate_1", ZoneType.GATE, capacity=250, area_sqm=70),
        Zone("aisle_A", ZoneType.CORRIDOR, capacity=500, area_sqm=300),
        Zone("aisle_B", ZoneType.CORRIDOR, capacity=500, area_sqm=300),
        Zone("food_court_1", ZoneType.FOOD_COURT, capacity=180, area_sqm=160),
        Zone("main_hall", ZoneType.EVENT_ZONE, capacity=2000, area_sqm=1200),
        Zone("exit_1", ZoneType.EXIT, capacity=300, area_sqm=90),
    ]
    for z in zones:
        sim.add_zone(z)

    sim.connect("gate_1", "aisle_A")
    sim.connect("aisle_A", "aisle_B")
    sim.connect("aisle_A", "food_court_1")
    sim.connect("aisle_B", "main_hall")
    sim.connect("main_hall", "exit_1")
    sim.connect("aisle_A", "exit_1")
    return sim


VENUE_BUILDERS = {
    "stadium": build_stadium,
    "airport": build_airport,
    "metro_station": build_metro_station,
    "concert_venue": build_concert_venue,
    "exhibition_hall": build_exhibition_hall,
}


# --------------------------------------------------------------------------- #
# Scenario generator
# --------------------------------------------------------------------------- #

class ScenarioGenerator:
    """
    Orchestrates running the simulator across many venue/scenario/seed
    combinations to build a large, varied synthetic dataset.
    """

    def __init__(self, output_dir: str = "data/generated", config: SimulationConfig = DEFAULT_CONFIG) -> None:
        self.output_dir = output_dir
        self.config = config
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_dataset(
        self,
        venues: Optional[List[str]] = None,
        scenarios: Optional[List[str]] = None,
        runs_per_combo: int = 5,
        duration_seconds: int = 1800,
        save_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Run the simulator across the cartesian product of venues,
        scenarios, and random seeds, concatenating results into one
        DataFrame.

        Args:
            venues: Venue template names (defaults to all in ``VENUE_BUILDERS``).
            scenarios: Scenario names (defaults to all ``ScenarioType`` values).
            runs_per_combo: Number of random-seed repeats per (venue, scenario) pair.
            duration_seconds: Simulated duration per run.
            save_path: If given, write the combined CSV here (else auto-named).

        Returns:
            A pandas DataFrame containing every generated record, with
            venue/scenario/run_id columns added for traceability.
        """
        venues = venues or list(VENUE_BUILDERS.keys())
        scenarios = scenarios or [s.value for s in ScenarioType]

        all_frames: List[pd.DataFrame] = []
        run_id = 0

        for venue_name in venues:
            builder = VENUE_BUILDERS.get(venue_name)
            if builder is None:
                logger.warning("Unknown venue '%s', skipping.", venue_name)
                continue

            for scenario in scenarios:
                for _ in range(runs_per_combo):
                    run_id += 1
                    seed = random.randint(0, 1_000_000)
                    run_config = replace(self.config, random_seed=seed)
                    sim = builder(run_config)

                    records = sim.run(scenario=scenario, duration_seconds=duration_seconds)
                    df = pd.DataFrame(records)
                    df["venue"] = venue_name
                    df["scenario"] = scenario
                    df["run_id"] = run_id
                    df["seed"] = seed
                    all_frames.append(df)

        combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        logger.info(
            "Generated dataset: %d rows across %d venues x %d scenarios x %d runs.",
            len(combined), len(venues), len(scenarios), runs_per_combo,
        )

        if save_path is None:
            save_path = os.path.join(self.output_dir, "generated_dataset.csv")
        combined.to_csv(save_path, index=False)
        logger.info("Saved dataset to %s", save_path)

        return combined
