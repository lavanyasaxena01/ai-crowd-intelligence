"""
crowd_simulator.py

Core simulation engine. Models a venue as a graph of ``Zone`` objects
(gates, corridors, waiting areas, food courts, event zones, exits)
connected by edges that agents move along. At every timestep the
simulator computes, per zone: occupancy, density, average movement
speed, inflow, and outflow.

The simulator is deliberately decoupled from any specific venue
layout — callers build the graph (see ``scenario_generator.py`` for
ready-made venue templates) and then step the simulation forward.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import networkx as nx
except ImportError:  # pragma: no cover - networkx is optional per spec
    nx = None

from .agent import Agent, AgentState
from .utils import (
    DEFAULT_CONFIG,
    SimulationConfig,
    ZoneType,
    clamp,
    get_logger,
    safe_divide,
    set_global_seed,
)

logger = get_logger(__name__)


@dataclass
class Zone:
    """
    A single functional area inside the venue (gate, corridor, food
    court, event zone, exit, etc.).

    Attributes:
        zone_id: Unique string identifier, e.g. ``"corridor_B"``.
        zone_type: Functional classification (see :class:`ZoneType`).
        capacity: Maximum comfortable occupancy for this zone.
        neighbors: IDs of zones directly reachable from this one.
        area_sqm: Physical area in square meters, used for density.
    """

    zone_id: str
    zone_type: ZoneType
    capacity: int
    neighbors: List[str] = field(default_factory=list)
    area_sqm: float = 100.0

    # Mutable per-timestep state
    occupants: List[Agent] = field(default_factory=list, repr=False)
    inflow_last_step: int = 0
    outflow_last_step: int = 0

    @property
    def people_count(self) -> int:
        return len(self.occupants)

    def density(self) -> float:
        """Occupancy as a fraction of rated capacity (0.0+, can exceed 1.0)."""
        return safe_divide(self.people_count, self.capacity)

    def physical_density(self) -> float:
        """People per square meter — a second, area-based density metric."""
        return safe_divide(self.people_count, self.area_sqm)


class CrowdSimulator:
    """
    Discrete-time crowd movement simulator over a graph of zones.

    Usage:
        sim = CrowdSimulator(config=my_config)
        sim.add_zone(Zone(...))
        sim.connect("gate_1", "corridor_A")
        sim.set_gates(["gate_1", "gate_2"])
        sim.set_exits(["exit_1"])
        records = sim.run(scenario="peak_traffic")
    """

    def __init__(self, config: SimulationConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self.zones: Dict[str, Zone] = {}
        self.gates: List[str] = []
        self.exits: List[str] = []
        self.food_courts: List[str] = []
        self.event_zones: List[str] = []
        self.current_time: int = 0
        self._agents: List[Agent] = []
        set_global_seed(config.random_seed)

    # ------------------------------------------------------------------ #
    # Graph construction
    # ------------------------------------------------------------------ #

    def add_zone(self, zone: Zone) -> None:
        """Register a zone with the simulator."""
        self.zones[zone.zone_id] = zone
        if zone.zone_type == ZoneType.GATE:
            self.gates.append(zone.zone_id)
        elif zone.zone_type == ZoneType.EXIT:
            self.exits.append(zone.zone_id)
        elif zone.zone_type == ZoneType.FOOD_COURT:
            self.food_courts.append(zone.zone_id)
        elif zone.zone_type == ZoneType.EVENT_ZONE:
            self.event_zones.append(zone.zone_id)

    def connect(self, zone_a: str, zone_b: str, bidirectional: bool = True) -> None:
        """Create a walkable edge between two zones."""
        self.zones[zone_a].neighbors.append(zone_b)
        if bidirectional:
            self.zones[zone_b].neighbors.append(zone_a)

    def to_networkx(self):
        """Return a NetworkX graph representation, if networkx is installed."""
        if nx is None:
            logger.warning("networkx not installed; skipping graph export.")
            return None
        graph = nx.Graph()
        for zone_id, zone in self.zones.items():
            graph.add_node(zone_id, zone_type=zone.zone_type.value, capacity=zone.capacity)
            for neighbor in zone.neighbors:
                graph.add_edge(zone_id, neighbor)
        return graph

    # ------------------------------------------------------------------ #
    # Pathfinding
    # ------------------------------------------------------------------ #

    def _shortest_path(self, start: str, end: str) -> List[str]:
        """Breadth-first search over the zone graph (no external deps)."""
        if start == end:
            return [start]
        visited = {start}
        queue: List[List[str]] = [[start]]
        while queue:
            path = queue.pop(0)
            node = path[-1]
            for neighbor in self.zones[node].neighbors:
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == end:
                    return new_path
                visited.add(neighbor)
                queue.append(new_path)
        return [start]  # no path found; stay put

    # ------------------------------------------------------------------ #
    # Arrival / departure rate modelling
    # ------------------------------------------------------------------ #

    def _arrival_rate(self, scenario: str, t: int, total_steps: int) -> float:
        """Compute the expected number of new arrivals this timestep."""
        cfg = self.config
        rate = cfg.base_arrival_rate

        if scenario == "peak_traffic":
            rate *= cfg.peak_multiplier
        elif scenario == "gate_closure":
            rate *= 0.4
        elif scenario == "emergency_evacuation":
            rate = 0.0  # nobody enters during an evacuation
        elif scenario == "food_court_rush":
            rate *= 1.5
        elif scenario == "event_ending":
            # Arrivals taper off sharply as the event wraps up.
            progress = safe_divide(t, total_steps)
            rate *= max(0.0, 1.0 - progress * 1.5)
        elif scenario == "random_congestion":
            rate *= random.uniform(0.7, 2.0)
        elif scenario == "uneven_crowd_distribution":
            rate *= random.uniform(0.5, 2.5)

        noise = random.gauss(0, cfg.arrival_noise_std * max(rate, 1.0))
        return max(0.0, rate + noise)

    def _departure_pull(self, scenario: str, t: int, total_steps: int) -> float:
        """Compute the relative pull (0-1) toward heading to an exit."""
        if scenario == "event_ending":
            progress = safe_divide(t, total_steps)
            return clamp(progress * self.config.surge_multiplier / 3.0, 0.05, 0.95)
        if scenario == "emergency_evacuation":
            return 0.95
        return 0.1

    # ------------------------------------------------------------------ #
    # Core simulation step
    # ------------------------------------------------------------------ #

    def _spawn_agents(self, count: int, scenario: str) -> None:
        """Create new agents at gates and assign them an initial path."""
        if not self.gates or count <= 0:
            return
        for _ in range(int(round(count))):
            gate = random.choice(self.gates)
            zone = self.zones[gate]

            # Decide a destination: event zone, food court, or exit.
            if scenario == "food_court_rush" and self.food_courts:
                destination = random.choice(self.food_courts)
            elif self.event_zones:
                destination = random.choice(self.event_zones)
            elif self.exits:
                destination = random.choice(self.exits)
            else:
                destination = gate

            path = self._shortest_path(gate, destination)
            agent = Agent(current_zone=gate)
            agent.assign_path(path[1:] if len(path) > 1 else [])
            zone.occupants.append(agent)
            zone.inflow_last_step += 1
            self._agents.append(agent)

    def _move_agents(self, scenario: str, t: int, total_steps: int) -> None:
        """Advance every active agent by one step, respecting congestion."""
        departure_pull = self._departure_pull(scenario, t, total_steps)
        blocked_zones = set()
        if scenario == "corridor_blockage":
            corridors = [z for z, zone in self.zones.items() if zone.zone_type == ZoneType.CORRIDOR]
            if corridors:
                blocked_zones = {random.choice(corridors)}

        for zone in self.zones.values():
            zone.inflow_last_step = 0
            zone.outflow_last_step = 0

        for agent in list(self._agents):
            if agent.state == AgentState.EXITED:
                continue

            origin_zone = self.zones[agent.current_zone]

            # Agents idling at a waiting/event zone may decide to head out.
            if not agent.path:
                if agent.current_zone in self.exits:
                    origin_zone.occupants.remove(agent)
                    agent.state = AgentState.EXITED
                    self._agents.remove(agent)
                    origin_zone.outflow_last_step += 1
                    continue
                if random.random() < departure_pull and self.exits:
                    exit_zone = random.choice(self.exits)
                    path = self._shortest_path(agent.current_zone, exit_zone)
                    agent.assign_path(path[1:] if len(path) > 1 else [])
                else:
                    continue  # stays put this step

            if not agent.path:
                continue

            next_zone_id = agent.path[0]
            if next_zone_id in blocked_zones:
                agent.register_wait()
                continue

            next_zone = self.zones[next_zone_id]
            # Congestion check: don't move into an already-overcapacity zone
            # unless the agent has grown impatient.
            if next_zone.density() >= 1.15 and not agent.is_impatient():
                agent.register_wait()
                continue

            origin_zone.occupants.remove(agent)
            origin_zone.outflow_last_step += 1
            agent.advance()
            next_zone.occupants.append(agent)
            next_zone.inflow_last_step += 1

            if next_zone_id in self.exits and not agent.path:
                next_zone.occupants.remove(agent)
                agent.state = AgentState.EXITED
                self._agents.remove(agent)
                next_zone.outflow_last_step += 1

    def _average_speed(self, zone: Zone) -> float:
        """
        Estimate average movement speed in a zone, which collapses as
        density approaches and exceeds capacity (crowd-crush effect).
        """
        density = zone.density()
        cfg = self.config
        if density <= 0:
            return cfg.base_walk_speed_mps
        congestion_factor = clamp(1.0 - (density ** cfg.speed_density_exponent), 0.0, 1.0)
        speed = cfg.min_speed_mps + (cfg.base_walk_speed_mps - cfg.min_speed_mps) * congestion_factor
        return round(max(speed, cfg.min_speed_mps), 3)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def step(self, scenario: str, t: int, total_steps: int) -> List[dict]:
        """
        Advance the simulation by a single timestep.

        Args:
            scenario: One of the ``ScenarioType`` values (as a string).
            t: Current timestep index.
            total_steps: Total number of steps in the run.

        Returns:
            A list of per-zone state dicts for this timestep.
        """
        arrivals = self._arrival_rate(scenario, t, total_steps)
        self._spawn_agents(arrivals, scenario)
        self._move_agents(scenario, t, total_steps)

        records = []
        for zone in self.zones.values():
            records.append(
                {
                    "timestamp": t * self.config.timestep_seconds,
                    "zone": zone.zone_id,
                    "zone_type": zone.zone_type.value,
                    "people_count": zone.people_count,
                    "capacity": zone.capacity,
                    "inflow": zone.inflow_last_step,
                    "outflow": zone.outflow_last_step,
                    "density": round(zone.density(), 4),
                    "avg_speed": self._average_speed(zone),
                }
            )
        self.current_time = t
        return records

    def run(self, scenario: str = "normal_traffic", duration_seconds: Optional[int] = None) -> List[dict]:
        """
        Run a full simulation from t=0 until ``duration_seconds`` elapses.

        Args:
            scenario: Scenario name (see :class:`ScenarioType`).
            duration_seconds: Overrides ``config.total_duration_seconds``.

        Returns:
            A flat list of per-zone, per-timestep state dicts.
        """
        duration = duration_seconds or self.config.total_duration_seconds
        total_steps = max(1, duration // self.config.timestep_seconds)

        logger.info("Starting simulation: scenario=%s steps=%d zones=%d", scenario, total_steps, len(self.zones))

        all_records: List[dict] = []
        for t in range(total_steps):
            all_records.extend(self.step(scenario, t, total_steps))

        logger.info("Simulation complete: %d records generated.", len(all_records))
        return all_records

    def reset(self) -> None:
        """Clear all agents and per-zone mutable state, keeping the graph."""
        self._agents.clear()
        for zone in self.zones.values():
            zone.occupants.clear()
            zone.inflow_last_step = 0
            zone.outflow_last_step = 0
        self.current_time = 0
