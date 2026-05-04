"""Pet state machine and stat decay.

This module is intentionally Qt-free so the logic can be unit-tested without
a running event loop. The Qt-aware driver lives in `controller.py`.

Lifecycle:
    pet = Pet.from_config(config, x=0.0, screen_width=1920.0)
    pet.tick(dt=0.1)         # call this many times a second
    pet.state                # current state
    pet.stats.hunger         # decayed value
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field

from tamagotchi.config import PetConfig, StatsConfig


class PetState(enum.StrEnum):
    IDLE = "idle"
    WALK = "walk"
    SLEEP = "sleep"


# Internal thresholds. Phase 4 hard-codes these; could later move to config.
LOW_ENERGY_THRESHOLD = 25.0
RESTED_ENERGY_THRESHOLD = 80.0
MIN_WALK_DURATION_SEC = 4.0
MAX_WALK_DURATION_SEC = 12.0

# Mood thresholds: a stat at or below this triggers the corresponding mood phrase.
HUNGRY_THRESHOLD = 30.0
SAD_THRESHOLD = 30.0
TIRED_THRESHOLD = 35.0

# Interaction effects (clamped to [0, 100]).
FEED_HUNGER_BOOST = 30.0
PET_HAPPINESS_BOOST = 5.0


@dataclass
class Stats:
    """Current stat values; mutated in place by `decay()`."""

    hunger: float
    energy: float
    happiness: float

    @classmethod
    def from_config(cls, cfg: StatsConfig) -> Stats:
        return cls(
            hunger=cfg.hunger.initial,
            energy=cfg.energy.initial,
            happiness=cfg.happiness.initial,
        )

    def decay(self, dt_sec: float, cfg: StatsConfig, *, sleeping: bool = False) -> None:
        """Decay stats by `dt_sec` seconds. If sleeping, energy regenerates."""
        dt_min = dt_sec / 60.0
        self.hunger = max(0.0, self.hunger - cfg.hunger.decay_per_min * dt_min)
        self.happiness = max(0.0, self.happiness - cfg.happiness.decay_per_min * dt_min)
        if sleeping:
            # Recover at 4x the decay rate while asleep.
            self.energy = min(100.0, self.energy + cfg.energy.decay_per_min * 4.0 * dt_min)
        else:
            self.energy = max(0.0, self.energy - cfg.energy.decay_per_min * dt_min)


@dataclass
class Pet:
    """Pet state machine + position. Pure logic; advanced by `tick()`."""

    config: PetConfig
    stats: Stats
    state: PetState = PetState.IDLE

    # Horizontal position in screen-space pixels. Y is fixed (ground level).
    x: float = 0.0
    facing: int = 1  # +1 right, -1 left
    screen_left: float = 0.0
    screen_right: float = 1920.0

    # Internal timers / accumulators (seconds).
    _idle_elapsed: float = 0.0
    _walk_remaining: float = 0.0
    _rng: random.Random = field(default_factory=random.Random)

    @classmethod
    def from_config(
        cls,
        config: PetConfig,
        *,
        x: float = 0.0,
        screen_left: float = 0.0,
        screen_right: float = 1920.0,
        rng: random.Random | None = None,
    ) -> Pet:
        return cls(
            config=config,
            stats=Stats.from_config(config.stats),
            x=x,
            screen_left=screen_left,
            screen_right=screen_right,
            _rng=rng if rng is not None else random.Random(),
        )

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def tick(self, dt: float) -> None:
        """Advance the simulation by `dt` seconds."""
        if dt <= 0:
            return
        self.stats.decay(dt, self.config.stats, sleeping=self.state is PetState.SLEEP)
        self._update_state(dt)
        if self.state is PetState.WALK:
            self._move(dt)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def _update_state(self, dt: float) -> None:
        match self.state:
            case PetState.IDLE:
                self._tick_idle(dt)
            case PetState.WALK:
                self._tick_walk(dt)
            case PetState.SLEEP:
                self._tick_sleep(dt)

    def _tick_idle(self, dt: float) -> None:
        self._idle_elapsed += dt

        # Tired -> sleep.
        if self.stats.energy <= LOW_ENERGY_THRESHOLD:
            self._enter(PetState.SLEEP)
            return

        # Long idle -> sleep.
        if self._idle_elapsed >= self.config.behavior.sleep_after_idle_sec:
            self._enter(PetState.SLEEP)
            return

        # Random per-minute chance to start walking. Convert to per-tick chance.
        chance_per_sec = self.config.behavior.idle_to_walk_chance / 60.0
        if self._rng.random() < chance_per_sec * dt:
            self._enter(PetState.WALK)

    def _tick_walk(self, dt: float) -> None:
        self._walk_remaining -= dt
        if self._walk_remaining <= 0:
            self._enter(PetState.IDLE)

    def _tick_sleep(self, _dt: float) -> None:
        if self.stats.energy >= RESTED_ENERGY_THRESHOLD:
            self._enter(PetState.IDLE)

    def _enter(self, new_state: PetState) -> None:
        if new_state is self.state:
            return
        self.state = new_state
        if new_state is PetState.IDLE:
            self._idle_elapsed = 0.0
        elif new_state is PetState.WALK:
            self._walk_remaining = self._rng.uniform(
                MIN_WALK_DURATION_SEC, MAX_WALK_DURATION_SEC
            )
            # Pick a direction biased toward the room center.
            center = (self.screen_left + self.screen_right) / 2.0
            self.facing = 1 if self.x < center else -1

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def _move(self, dt: float) -> None:
        speed = self.config.behavior.walk_speed_px_per_sec
        self.x += speed * self.facing * dt
        # Edge bounce: clamp and flip facing if we hit a wall.
        if self.x <= self.screen_left:
            self.x = self.screen_left
            self.facing = 1
        elif self.x >= self.screen_right:
            self.x = self.screen_right
            self.facing = -1

    # ------------------------------------------------------------------
    # External events
    # ------------------------------------------------------------------
    def force_state(self, new_state: PetState) -> None:
        """Bypass the transition logic — useful for tray actions and tests."""
        self._enter(new_state)

    def feed(self, amount: float = FEED_HUNGER_BOOST) -> None:
        """Restore hunger by `amount`. Wakes the pet if asleep."""
        self.stats.hunger = min(100.0, self.stats.hunger + amount)
        if self.state is PetState.SLEEP:
            self._enter(PetState.IDLE)

    def pet_action(self, amount: float = PET_HAPPINESS_BOOST) -> None:
        """Boost happiness by `amount`. Named `pet_action` to avoid shadowing the type."""
        self.stats.happiness = min(100.0, self.stats.happiness + amount)

    def current_mood(self) -> str | None:
        """Return a mood key when a stat is below threshold, else None.

        Priority: hungry > tired > sad. Sleeping pets never report 'tired'.
        """
        if self.stats.hunger <= HUNGRY_THRESHOLD:
            return "hungry"
        if self.state is not PetState.SLEEP and self.stats.energy <= TIRED_THRESHOLD:
            return "tired"
        if self.stats.happiness <= SAD_THRESHOLD:
            return "sad"
        return None
