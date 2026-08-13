"""
agent.py

Defines the ``Agent`` class: a single simulated person moving through
the venue graph. Agents are intentionally lightweight (no physics
engine) since the simulator operates at the zone-aggregate level, but
each agent tracks its own path and state so behaviours like "food
court detour" or "panic evacuation" can be modelled per-person.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import List, Optional


_id_counter = itertools.count(1)


class AgentState:
    """Lifecycle states an agent can be in."""

    ARRIVING = "arriving"
    MOVING = "moving"
    WAITING = "waiting"
    DEPARTING = "departing"
    EXITED = "exited"


@dataclass
class Agent:
    """
    A single simulated crowd member.

    Attributes:
        agent_id: Unique integer identifier.
        current_zone: ID of the zone the agent currently occupies.
        destination_zone: ID of the zone the agent is heading toward.
        path: Remaining sequence of zone IDs to traverse.
        state: Current lifecycle state (see :class:`AgentState`).
        patience: Number of timesteps the agent will wait in
            congestion before attempting to reroute.
        speed_factor: Per-agent multiplier on the base walk speed,
            capturing natural variation (children, elderly, groups).
    """

    current_zone: str
    destination_zone: Optional[str] = None
    path: List[str] = field(default_factory=list)
    state: str = AgentState.ARRIVING
    patience: int = 5
    speed_factor: float = field(default_factory=lambda: round(random.uniform(0.75, 1.25), 2))
    agent_id: int = field(default_factory=lambda: next(_id_counter))
    waited_steps: int = 0

    def advance(self) -> Optional[str]:
        """
        Move the agent one step along its path.

        Returns:
            The new current zone ID, or ``None`` if the agent has no
            further path (it has reached its destination).
        """
        if not self.path:
            self.state = AgentState.EXITED if self.destination_zone is None else AgentState.WAITING
            return None

        next_zone = self.path.pop(0)
        self.current_zone = next_zone
        self.waited_steps = 0
        self.state = AgentState.MOVING
        if not self.path:
            self.state = AgentState.EXITED if self.destination_zone is None else AgentState.WAITING
        return next_zone

    def register_wait(self) -> None:
        """Increment the agent's waited-step counter (called when blocked)."""
        self.waited_steps += 1
        self.state = AgentState.WAITING

    def is_impatient(self) -> bool:
        """Whether the agent has waited long enough to want to reroute."""
        return self.waited_steps >= self.patience

    def assign_path(self, path: List[str]) -> None:
        """Assign a fresh path (e.g., after rerouting) to the agent."""
        self.path = list(path)
        self.destination_zone = path[-1] if path else None
        self.waited_steps = 0
