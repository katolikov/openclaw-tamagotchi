"""Dialogue book: state-keyed phrases the pet can utter.

Format (`dialogues.yaml`):
    idle:  ["Hmm...", "..."]
    walk:  ["Off to explore!", ...]
    sleep: ["Zzz..."]
    hungry: ["..."]   # optional mood overrides; selected via DialogueBook.pick_for_mood

Validation rules: every key must map to a non-empty list of non-empty strings.
"""

from __future__ import annotations

import random
from pathlib import Path

import yaml

from tamagotchi.config import ConfigError
from tamagotchi.pet import PetState

DIALOGUE_FILENAME = "dialogues.yaml"


class DialogueBook:
    """Phrases keyed by state (and optional moods). Pure logic; no Qt."""

    def __init__(
        self,
        phrases: dict[str, list[str]],
        rng: random.Random | None = None,
    ) -> None:
        self._phrases = phrases
        self._rng = rng if rng is not None else random.Random()

    @classmethod
    def load(cls, pet_dir: Path, *, rng: random.Random | None = None) -> DialogueBook:
        path = pet_dir / DIALOGUE_FILENAME
        if not path.is_file():
            raise ConfigError(f"missing dialogue file: {path}")
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {path}: {e}") from e

        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: top-level must be a mapping")

        phrases: dict[str, list[str]] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not key:
                raise ConfigError(f"{path}: keys must be non-empty strings")
            if not isinstance(value, list) or not value:
                raise ConfigError(f"{path}: '{key}' must be a non-empty list")
            cleaned: list[str] = []
            for i, phrase in enumerate(value):
                if not isinstance(phrase, str) or not phrase.strip():
                    raise ConfigError(
                        f"{path}: '{key}'[{i}] must be a non-empty string"
                    )
                cleaned.append(phrase)
            phrases[key] = cleaned

        # Require at least an "idle" entry so the pet always has something to say.
        if "idle" not in phrases:
            raise ConfigError(f"{path}: 'idle' key is required")

        return cls(phrases, rng=rng)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def has(self, key: str) -> bool:
        return key in self._phrases

    def pick(self, key: str) -> str:
        """Pick a random phrase for `key`, falling back to 'idle' if missing."""
        bucket = self._phrases.get(key) or self._phrases["idle"]
        return self._rng.choice(bucket)

    def pick_for_state(self, state: PetState) -> str:
        return self.pick(state.value)

    def pick_for_mood(self, mood: str) -> str | None:
        """Return a phrase for a non-state mood key (e.g. 'hungry'), or None if absent."""
        if mood not in self._phrases:
            return None
        return self._rng.choice(self._phrases[mood])
