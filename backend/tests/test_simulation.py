"""Tests for the crowd simulation engine."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulation.crowd_simulator import CrowdSimulator, Zone
from simulation.scenario_generator import build_stadium, build_airport, VENUE_BUILDERS
from simulation.utils import SimulationConfig, ZoneType


def test_zone_density_and_capacity():
    zone = Zone("z1", ZoneType.CORRIDOR, capacity=100)
    assert zone.people_count == 0
    assert zone.density() == 0.0


def test_simulator_basic_run_produces_records():
    config = SimulationConfig(random_seed=1, timestep_seconds=10, total_duration_seconds=200)
    sim = build_stadium(config)
    records = sim.run(scenario="normal_traffic")
    assert len(records) > 0
    for record in records[:5]:
        assert "zone" in record
        assert "density" in record
        assert record["density"] >= 0
        assert record["avg_speed"] >= config.min_speed_mps


def test_all_venue_templates_build():
    for name, builder in VENUE_BUILDERS.items():
        sim = builder()
        assert len(sim.zones) > 0
        assert len(sim.gates) > 0
        assert len(sim.exits) > 0


def test_peak_traffic_produces_more_people_than_normal():
    config = SimulationConfig(random_seed=42, timestep_seconds=10, total_duration_seconds=600)
    sim_normal = build_airport(SimulationConfig(random_seed=42, timestep_seconds=10, total_duration_seconds=600))
    sim_peak = build_airport(SimulationConfig(random_seed=42, timestep_seconds=10, total_duration_seconds=600))

    normal_records = sim_normal.run(scenario="normal_traffic")
    peak_records = sim_peak.run(scenario="peak_traffic")

    normal_total = sum(r["people_count"] for r in normal_records)
    peak_total = sum(r["people_count"] for r in peak_records)
    assert peak_total >= normal_total


def test_gate_closure_reduces_arrivals():
    cfg = lambda: SimulationConfig(random_seed=7, timestep_seconds=10, total_duration_seconds=400)
    sim_normal = build_stadium(cfg())
    sim_closed = build_stadium(cfg())

    normal_records = sim_normal.run(scenario="normal_traffic")
    closed_records = sim_closed.run(scenario="gate_closure")

    normal_inflow = sum(r["inflow"] for r in normal_records)
    closed_inflow = sum(r["inflow"] for r in closed_records)
    assert closed_inflow <= normal_inflow
