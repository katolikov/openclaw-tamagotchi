"""Tests for pet.yaml schema and loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tamagotchi.config import (
    AnimationConfig,
    BehaviorConfig,
    ConfigError,
    PetConfig,
    load_pet_config,
)

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


# ---- happy path -------------------------------------------------------------
def test_loads_real_claw_config() -> None:
    cfg = load_pet_config(PETS_DIR / "claw")
    assert cfg.name == "Claw"
    assert cfg.species == "pirate_cat"
    assert "idle" in cfg.sprites
    assert cfg.sprites["idle"].frames == 8
    assert cfg.sprites["idle"].fps == 6
    assert cfg.sprites["idle"].loop is True
    assert cfg.behavior.speech_interval_sec == (12.0, 30.0)
    assert cfg.stats.hunger.initial == 100
    assert cfg.stats.hunger.decay_per_min == 0.5


# ---- error paths ------------------------------------------------------------
def _write_yaml(tmp_path: Path, body: str) -> Path:
    pet_dir = tmp_path / "testpet"
    pet_dir.mkdir()
    (pet_dir / "pet.yaml").write_text(textwrap.dedent(body), encoding="utf-8")
    return pet_dir


def test_missing_file(tmp_path: Path) -> None:
    pet_dir = tmp_path / "no_config_here"
    pet_dir.mkdir()
    with pytest.raises(ConfigError, match="missing config file"):
        load_pet_config(pet_dir)


def test_malformed_yaml(tmp_path: Path) -> None:
    pet_dir = _write_yaml(tmp_path, "name: 'Claw\nbroken: [")
    with pytest.raises(ConfigError, match="YAML parse error"):
        load_pet_config(pet_dir)


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    pet_dir = _write_yaml(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ConfigError, match="top-level must be a mapping"):
        load_pet_config(pet_dir)


def test_missing_required_field(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        # species missing
        sprites:
          idle: { file: "sprites/idle.png", frames: 1, fps: 1 }
        """,
    )
    with pytest.raises(ConfigError, match="species"):
        load_pet_config(pet_dir)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        species: "y"
        speceis_typo: "oops"
        sprites:
          idle: { file: "sprites/idle.png", frames: 1, fps: 1 }
        """,
    )
    with pytest.raises(ConfigError):
        load_pet_config(pet_dir)


def test_idle_sprite_required(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        species: "y"
        sprites:
          walk: { file: "w.png", frames: 4, fps: 8 }
        """,
    )
    with pytest.raises(ConfigError, match="idle"):
        load_pet_config(pet_dir)


def test_zero_frames_rejected(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        species: "y"
        sprites:
          idle: { file: "i.png", frames: 0, fps: 1 }
        """,
    )
    with pytest.raises(ConfigError):
        load_pet_config(pet_dir)


def test_speech_interval_order(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        species: "y"
        sprites:
          idle: { file: "i.png", frames: 1, fps: 1 }
        behavior:
          speech_interval_sec: [90, 30]
        """,
    )
    with pytest.raises(ConfigError, match="speech_interval_sec"):
        load_pet_config(pet_dir)


# ---- defaults --------------------------------------------------------------
def test_behavior_defaults_apply(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        species: "y"
        sprites:
          idle: { file: "i.png", frames: 1, fps: 1 }
        """,
    )
    cfg = load_pet_config(pet_dir)
    assert cfg.behavior == BehaviorConfig()
    assert cfg.role is None


def test_animation_loop_default_true() -> None:
    a = AnimationConfig(file=Path("x.png"), frames=4, fps=8)
    assert a.loop is True


def test_pet_config_is_frozen() -> None:
    cfg = load_pet_config(PETS_DIR / "claw")
    with pytest.raises(Exception):  # noqa: B017 — pydantic raises on frozen mutation
        cfg.name = "Changed"


def test_role_field_optional(tmp_path: Path) -> None:
    pet_dir = _write_yaml(
        tmp_path,
        """
        name: "x"
        species: "y"
        role: "researcher"
        sprites:
          idle: { file: "i.png", frames: 1, fps: 1 }
        """,
    )
    cfg = load_pet_config(pet_dir)
    assert cfg.role == "researcher"


def test_construct_petconfig_directly() -> None:
    """Sanity: can build a PetConfig in code (useful for tests in later phases)."""
    cfg = PetConfig(
        name="Test",
        species="test",
        sprites={"idle": AnimationConfig(file=Path("idle.png"), frames=1, fps=1)},
    )
    assert cfg.name == "Test"
