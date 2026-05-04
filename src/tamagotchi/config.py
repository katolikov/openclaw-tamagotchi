"""Pet configuration: pydantic models and YAML loader for `pet.yaml`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# Two-element tuples in YAML come through as lists; pydantic normalizes them.
RangeSeconds = Annotated[
    tuple[float, float],
    Field(description="(min_seconds, max_seconds), inclusive."),
]


class ConfigError(ValueError):
    """Raised when a pet config file is missing, unreadable, or fails validation."""


class _StrictModel(BaseModel):
    """Base for all config models: forbid unknown keys to catch typos."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AnimationConfig(_StrictModel):
    """One animation state: a sprite sheet plus playback parameters."""

    file: Path = Field(description="Path to the sprite sheet, relative to the pet folder.")
    frames: int = Field(gt=0, description="Number of frames in the horizontal strip.")
    fps: float = Field(gt=0, description="Frames per second.")
    loop: bool = Field(default=True)


class BehaviorConfig(_StrictModel):
    idle_to_walk_chance: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Per-minute probability of starting to walk."
    )
    walk_speed_px_per_sec: float = Field(default=40.0, gt=0.0)
    sleep_after_idle_sec: float = Field(default=120.0, gt=0.0)
    speech_interval_sec: RangeSeconds = (30.0, 90.0)

    @field_validator("speech_interval_sec", mode="before")
    @classmethod
    def _coerce_range(cls, v: object) -> object:
        # YAML lists -> tuple; also accept (a, b).
        if isinstance(v, list):
            if len(v) != 2:
                raise ValueError(f"speech_interval_sec must have exactly 2 values, got {len(v)}")
            return (float(v[0]), float(v[1]))
        return v

    @field_validator("speech_interval_sec")
    @classmethod
    def _check_range_order(cls, v: tuple[float, float]) -> tuple[float, float]:
        lo, hi = v
        if lo <= 0 or hi <= 0:
            raise ValueError("speech_interval_sec values must be > 0")
        if lo > hi:
            raise ValueError(f"speech_interval_sec min ({lo}) must be <= max ({hi})")
        return v


class StatConfig(_StrictModel):
    initial: float = Field(ge=0.0, le=100.0)
    decay_per_min: float = Field(ge=0.0, description="Units lost per minute.")


class StatsConfig(_StrictModel):
    """Classic tamagotchi stats; each decays over time."""

    hunger: StatConfig = StatConfig(initial=100.0, decay_per_min=0.5)
    energy: StatConfig = StatConfig(initial=100.0, decay_per_min=0.3)
    happiness: StatConfig = StatConfig(initial=100.0, decay_per_min=0.4)


class PetConfig(_StrictModel):
    """Top-level schema for `pet.yaml`."""

    name: str = Field(min_length=1)
    species: str = Field(min_length=1)
    role: str | None = Field(
        default=None,
        description="Optional role tag (e.g. 'researcher'); used by the dialogue system.",
    )
    sprites: dict[str, AnimationConfig]
    behavior: BehaviorConfig = BehaviorConfig()
    stats: StatsConfig = StatsConfig()

    @field_validator("sprites")
    @classmethod
    def _require_idle(cls, v: dict[str, AnimationConfig]) -> dict[str, AnimationConfig]:
        if "idle" not in v:
            raise ValueError("sprites must include an 'idle' animation")
        return v


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
PET_CONFIG_FILENAME = "pet.yaml"


def load_pet_config(pet_dir: Path) -> PetConfig:
    """Load and validate `<pet_dir>/pet.yaml`.

    Raises ConfigError with a human-readable message on any failure
    (missing file, malformed YAML, schema validation errors).
    """
    config_path = pet_dir / PET_CONFIG_FILENAME
    if not config_path.is_file():
        raise ConfigError(f"missing config file: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {config_path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: top-level must be a mapping, got {type(raw).__name__}")

    try:
        return PetConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"invalid {config_path}:\n{e}") from e


def resolve_sprite_path(pet_dir: Path, anim: AnimationConfig) -> Path:
    """Resolve an animation's `file` against the pet folder."""
    return (pet_dir / anim.file).resolve()
