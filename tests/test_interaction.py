"""Tests for Pet.feed/pet_action/current_mood and persistence."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from tamagotchi.config import PetConfig, load_pet_config
from tamagotchi.pet import (
    HUNGRY_THRESHOLD,
    SAD_THRESHOLD,
    TIRED_THRESHOLD,
    Pet,
    PetState,
    Stats,
)
from tamagotchi.state import (
    SCHEMA_VERSION,
    load_stats,
    save_stats,
    state_path,
)

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


@pytest.fixture
def cfg() -> PetConfig:
    return load_pet_config(PETS_DIR / "claw")


# ---- Pet interactions ------------------------------------------------------
def test_feed_boosts_hunger(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.hunger = 30.0
    pet.feed(amount=20.0)
    assert pet.stats.hunger == 50.0


def test_feed_clamped_to_100(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.hunger = 95.0
    pet.feed(amount=50.0)
    assert pet.stats.hunger == 100.0


def test_feed_wakes_pet(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.force_state(PetState.SLEEP)
    pet.feed()
    assert pet.state is PetState.IDLE


def test_pet_action_boosts_happiness(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.happiness = 50.0
    pet.pet_action(amount=10.0)
    assert pet.stats.happiness == 60.0


def test_pet_action_clamped_to_100(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.happiness = 99.0
    pet.pet_action(amount=10.0)
    assert pet.stats.happiness == 100.0


# ---- Mood ------------------------------------------------------------------
def test_no_mood_when_stats_high(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    assert pet.current_mood() is None


def test_hungry_mood(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.hunger = HUNGRY_THRESHOLD - 0.1
    assert pet.current_mood() == "hungry"


def test_tired_mood_only_when_awake(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.energy = TIRED_THRESHOLD - 0.1
    assert pet.current_mood() == "tired"
    pet.force_state(PetState.SLEEP)
    # While asleep we don't surface 'tired' mood (the pet is already resting).
    assert pet.current_mood() != "tired"


def test_sad_mood(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.happiness = SAD_THRESHOLD - 0.1
    assert pet.current_mood() == "sad"


def test_mood_priority_hungry_over_tired(cfg: PetConfig) -> None:
    pet = Pet.from_config(cfg)
    pet.stats.hunger = 5
    pet.stats.energy = 5
    pet.stats.happiness = 5
    assert pet.current_mood() == "hungry"


# ---- Persistence ----------------------------------------------------------
@contextmanager
def _isolated_state_dir(tmp_path: Path) -> Iterator[None]:
    with patch("tamagotchi.state.state_dir", lambda: tmp_path):
        yield


def test_save_then_load_roundtrip(cfg: PetConfig, tmp_path: Path) -> None:
    with _isolated_state_dir(tmp_path):
        stats = Stats(hunger=42.0, energy=55.5, happiness=12.3)
        save_stats("Claw", stats)
        loaded = load_stats("Claw")
        assert loaded is not None
        assert loaded.hunger == pytest.approx(42.0)
        assert loaded.energy == pytest.approx(55.5)
        assert loaded.happiness == pytest.approx(12.3)


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    with _isolated_state_dir(tmp_path):
        assert load_stats("nonexistent") is None


def test_load_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    with _isolated_state_dir(tmp_path):
        path = state_path("Claw")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid json", encoding="utf-8")
        assert load_stats("Claw") is None


def test_load_returns_none_for_wrong_schema(tmp_path: Path) -> None:
    with _isolated_state_dir(tmp_path):
        path = state_path("Claw")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": SCHEMA_VERSION + 1, "stats": {}}),
            encoding="utf-8",
        )
        assert load_stats("Claw") is None


def test_pet_name_sanitized_in_path(tmp_path: Path) -> None:
    with _isolated_state_dir(tmp_path):
        path = state_path("Bad/Name With:Spaces")
        # No path separators or whitespace in the resulting filename.
        assert "/" not in path.name
        assert " " not in path.name
        assert ":" not in path.name
        assert path.name.endswith(".json")
