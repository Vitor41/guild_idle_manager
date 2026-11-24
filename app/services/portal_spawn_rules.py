"""Immutable, versioned rules for new regional portal spawn rolls."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PortalSpawnRules:
    version: str
    base_chance_pp: int = 8
    failure_increment_pp: int = 1
    base_chance_cap_pp: int = 20
    explorer_bonus_cap_pp: int = 5
    cooldown_hours: int = 24
    entry_window_hours: int = 12
    max_failure_stacks: int = 12

    def __post_init__(self) -> None:
        integer_parameters = (
            self.base_chance_pp,
            self.failure_increment_pp,
            self.base_chance_cap_pp,
            self.explorer_bonus_cap_pp,
            self.cooldown_hours,
            self.entry_window_hours,
            self.max_failure_stacks,
        )
        if not self.version or any(type(value) is not int for value in integer_parameters):
            raise ValueError("Portal spawn rule parameters must be named integers.")
        if self.base_chance_pp < 0 or self.failure_increment_pp <= 0:
            raise ValueError("Portal spawn chance and failure increment are out of range.")
        if self.base_chance_cap_pp < self.base_chance_pp:
            raise ValueError("The base chance cap cannot be below the base chance.")
        if self.explorer_bonus_cap_pp < 0 or self.base_chance_cap_pp + self.explorer_bonus_cap_pp >= 100:
            raise ValueError("Portal spawn chance must remain below 100%.")
        if self.cooldown_hours <= 0 or self.entry_window_hours <= 0:
            raise ValueError("Portal spawn deadlines must be positive.")
        if self.max_failure_stacks < ceil(
            (self.base_chance_cap_pp - self.base_chance_pp) / self.failure_increment_pp
        ):
            raise ValueError("The failure stack limit must be able to reach the base chance cap.")

    @property
    def cooldown_seconds(self) -> int:
        return self.cooldown_hours * 3600

    @property
    def entry_window_seconds(self) -> int:
        return self.entry_window_hours * 3600

    def max_stack(self) -> int:
        return min(
            self.max_failure_stacks,
            ceil((self.base_chance_cap_pp - self.base_chance_pp) / self.failure_increment_pp),
        )

    def chance_percentages(self, failure_stacks: int, explorer_bonus_pp: int) -> tuple[int, int, int]:
        base = min(
            self.base_chance_cap_pp,
            self.base_chance_pp + max(0, int(failure_stacks)) * self.failure_increment_pp,
        )
        explorer = min(self.explorer_bonus_cap_pp, max(0, int(explorer_bonus_pp)))
        return base, explorer, min(99, base + explorer)


CURRENT_PORTAL_SPAWN_RULES_VERSION = "portal-spawn-v1"
PORTAL_SPAWN_RULES: Mapping[str, PortalSpawnRules] = MappingProxyType({
    CURRENT_PORTAL_SPAWN_RULES_VERSION: PortalSpawnRules(
        version=CURRENT_PORTAL_SPAWN_RULES_VERSION,
    ),
})


def get_portal_spawn_rules(version: str | None) -> PortalSpawnRules | None:
    if version is None:
        return None
    return PORTAL_SPAWN_RULES.get(version)
