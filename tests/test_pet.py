"""Tests for the Pet state machine and Stats decay."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from tamagotchi.config import PetConfig, load_pet_config
from tamagotchi.pet import (
    LOW_ENERGY_THRESHOLD,
    MAX_WALK_DURATION_SEC,
    RESTED_ENERGY_THRESHOLD,
    Pet,
    PetState,
    Stats,
)

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


@pytest.fixture
def cfg() -> PetConfig:
    return load_pet_config(PETS_DIR / "claw")


# ---- Stats decay -----------------------------------------------------------
def test_stats_decay_over_time(cfg: PetConfig) -> None:
    stats = Stats.from_config(cfg.stats)
    h0, e0, p0 = stats.hunger, stats.energy, stats.happiness

    # 60 seconds == 1 minute => exactly `decay_per_min` lost.
    stats.decay(60.0, cfg.stats, sleeping=False)
    assert stats.hunger == pytest.approx(h0 - cfg.stats.hunger.decay_per_min, rel=1e-6)
    assert stats.energy == pytest.approx(e0 - cfg.stats.energy.decay_per_min, rel=1e-6)
    assert stats.happiness == pytest.approx(p0 - cfg.stats.happiness.decay_per_min, rel=1e-6)


def test_stats_clamped_at_zero(cfg: PetConfig) -> None:
    stats = Stats(hunger=0.1, energy=0.1, happiness=0.1)
    stats.decay(60_000.0, cfg.stats, sleeping=False)
    assert stats.hunger == 0.0
    assert stats.energy == 0.0
    assert stats.happiness == 0.0


def test_sleeping_regenerates_energy(cfg: PetConfig) -> None:
    stats = Stats(hunger=100, energy=20, happiness=100)
    stats.decay(60.0, cfg.stats, sleeping=True)
    assert stats.energy > 20  # regenerated
    assert stats.energy <= 100


def test_energy_capped_at_100(cfg: PetConfig) -> None:
    stats = Stats(hunger=100, energy=99.5, happiness=100)
    stats.decay(60_000.0, cfg.stats, sleeping=True)
    assert stats.energy == 100.0


# ---- State transitions -----------------------------------------------------
def test_initial_state_is_idle(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    assert pet.state is PetState.IDLE


def test_idle_to_sleep_when_energy_low(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, rng=random.Random(0))
    pet.stats.energy = LOW_ENERGY_THRESHOLD - 0.1
    pet.tick(0.1)
    assert pet.state is PetState.SLEEP


def test_sleep_to_idle_when_rested(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, rng=random.Random(0))
    pet.force_state(PetState.SLEEP)
    pet.stats.energy = RESTED_ENERGY_THRESHOLD + 0.1
    pet.tick(0.1)
    assert pet.state is PetState.IDLE


def test_idle_to_sleep_after_long_idle(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, rng=random.Random(42))
    # Force a generous timeout that won't be tripped by the random walk chance.
    # Tick in 1-second steps; with idle_to_walk_chance=0.3/min the per-second
    # probability is 0.005 — Random(42) shouldn't trip it before sleep_after_idle_sec.
    threshold = cfg.behavior.sleep_after_idle_sec
    for _ in range(int(threshold) + 5):
        pet.tick(1.0)
        if pet.state is PetState.SLEEP:
            return
    pytest.fail("expected pet to fall asleep after sleep_after_idle_sec")


def test_idle_to_walk_via_force_state(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, rng=random.Random(0), screen_left=0, screen_right=1000)
    pet.force_state(PetState.WALK)
    assert pet.state is PetState.WALK
    assert pet._walk_remaining > 0
    assert pet._walk_remaining <= MAX_WALK_DURATION_SEC


def test_walk_returns_to_idle_after_duration(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, rng=random.Random(0), screen_left=0, screen_right=10_000)
    pet.force_state(PetState.WALK)
    # Tick past the maximum walk duration.
    pet.tick(MAX_WALK_DURATION_SEC + 1.0)
    assert pet.state is PetState.IDLE


# ---- Movement --------------------------------------------------------------
def test_walk_moves_in_facing_direction(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, x=500.0, screen_left=0, screen_right=1000, rng=random.Random(0))
    pet.force_state(PetState.WALK)
    pet._walk_remaining = 100.0  # ensure WALK persists through the tick
    pet.facing = 1
    speed = cfg.behavior.walk_speed_px_per_sec
    pet.tick(1.0)
    assert pet.x == pytest.approx(500.0 + speed, rel=1e-3)


def test_edge_turnaround(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, x=999.0, screen_left=0, screen_right=1000, rng=random.Random(0))
    pet.force_state(PetState.WALK)
    pet._walk_remaining = 100.0
    pet.facing = 1
    pet.tick(10.0)  # would carry far past the right edge
    assert pet.x == 1000.0
    assert pet.facing == -1


def test_no_movement_while_idle(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg, x=500.0, screen_left=0, screen_right=1000, rng=random.Random(0))
    pet.tick(1.0)
    if pet.state is PetState.IDLE:
        assert pet.x == 500.0
