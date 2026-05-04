"""Persistent state: hunger/energy/happiness saved between runs.

State lives at:
    <user_config_dir>/tamagotchi/<pet_name>.json

We deliberately persist only the stats (and a schema version). State that's
trivial to recompute — current animation state, position, walk timer — is
re-derived on launch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

from tamagotchi.pet import Stats

APP_NAME = "tamagotchi"
SCHEMA_VERSION = 1


def state_dir() -> Path:
    """Return the platform-appropriate config directory (created if missing)."""
    p = Path(user_config_dir(APP_NAME))
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path(pet_name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in pet_name).lower()
    return state_dir() / f"{safe}.json"


def save_stats(pet_name: str, stats: Stats) -> Path:
    """Atomically write stats to the on-disk state file."""
    payload: dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "stats": {
            "hunger": stats.hunger,
            "energy": stats.energy,
            "happiness": stats.happiness,
        },
    }
    target = state_path(pet_name)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)  # atomic on POSIX/Windows for same-filesystem writes
    return target


def load_stats(pet_name: str) -> Stats | None:
    """Load saved stats, returning None on any error (caller falls back to config defaults)."""
    path = state_path(pet_name)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("version") != SCHEMA_VERSION:
        return None
    s = raw.get("stats")
    if not isinstance(s, dict):
        return None
    try:
        return Stats(
            hunger=float(s["hunger"]),
            energy=float(s["energy"]),
            happiness=float(s["happiness"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
