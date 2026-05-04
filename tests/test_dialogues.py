"""Tests for DialogueBook loader and selection."""

from __future__ import annotations

import random
import textwrap
from pathlib import Path

import pytest

from tamagotchi.config import ConfigError
from tamagotchi.dialogues import DialogueBook
from tamagotchi.pet import PetState

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


def _write(tmp_path: Path, body: str) -> Path:
    pet_dir = tmp_path / "p"
    pet_dir.mkdir()
    (pet_dir / "dialogues.yaml").write_text(textwrap.dedent(body), encoding="utf-8")
    return pet_dir


def test_loads_real_claw_dialogues() -> None:
    book = DialogueBook.load(PETS_DIR / "claw")
    assert book.has("idle")
    assert book.has("walk")
    assert book.has("sleep")
    assert book.has("hungry")  # mood key


def test_pick_for_state_returns_valid_phrase() -> None:
    rng = random.Random(0)
    book = DialogueBook.load(PETS_DIR / "claw", rng=rng)
    phrase = book.pick_for_state(PetState.IDLE)
    assert isinstance(phrase, str)
    assert phrase.strip() != ""


def test_unknown_state_falls_back_to_idle(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        idle:
          - "only idle"
        """,
    )
    book = DialogueBook.load(pet_dir, rng=random.Random(0))
    # 'walk' is missing — should still return an idle phrase.
    assert book.pick("walk") == "only idle"


def test_pick_for_mood_returns_none_for_unknown(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        idle:
          - "x"
        """,
    )
    book = DialogueBook.load(pet_dir, rng=random.Random(0))
    assert book.pick_for_mood("hungry") is None


def test_pick_for_mood_returns_phrase_when_present(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        idle:
          - "x"
        hungry:
          - "feed me"
        """,
    )
    book = DialogueBook.load(pet_dir, rng=random.Random(0))
    assert book.pick_for_mood("hungry") == "feed me"


def test_missing_file(tmp_path: Path) -> None:
    pet_dir = tmp_path / "empty"
    pet_dir.mkdir()
    with pytest.raises(ConfigError, match="missing dialogue file"):
        DialogueBook.load(pet_dir)


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    pet_dir = _write(tmp_path, "- nope\n")
    with pytest.raises(ConfigError):
        DialogueBook.load(pet_dir)


def test_idle_required(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        walk:
          - "x"
        """,
    )
    with pytest.raises(ConfigError, match="idle"):
        DialogueBook.load(pet_dir)


def test_empty_phrase_list_rejected(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        idle: []
        """,
    )
    with pytest.raises(ConfigError, match="non-empty list"):
        DialogueBook.load(pet_dir)


def test_empty_phrase_string_rejected(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        idle:
          - "valid"
          - "   "
        """,
    )
    with pytest.raises(ConfigError):
        DialogueBook.load(pet_dir)


def test_selection_uses_provided_rng(tmp_path: Path) -> None:
    pet_dir = _write(
        tmp_path,
        """
        idle:
          - "a"
          - "b"
          - "c"
        """,
    )
    a = DialogueBook.load(pet_dir, rng=random.Random(1))
    b = DialogueBook.load(pet_dir, rng=random.Random(1))
    # Same seed -> same pick sequence.
    assert a.pick("idle") == b.pick("idle")
    assert a.pick("idle") == b.pick("idle")
