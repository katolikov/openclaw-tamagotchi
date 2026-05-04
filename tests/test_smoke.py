"""Smoke tests: imports work and the pet window can be constructed off-screen."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from tamagotchi import __version__
from tamagotchi.config import load_pet_config
from tamagotchi.window import PetWindow

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


def test_version_string() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 1


def test_pet_window_constructs(qapp: QApplication) -> None:
    pet_dir = PETS_DIR / "claw"
    assert pet_dir.is_dir(), f"missing pet dir: {pet_dir}"
    config = load_pet_config(pet_dir)
    win = PetWindow(pet_dir=pet_dir, config=config)
    # Window should have non-zero size after loading the sprite sheet.
    assert win.width() > 0
    assert win.height() > 0
    # Phase 2: animation player exists and is on frame 0.
    assert win._player is not None
    assert win._player.index == 0
    assert win._player.sheet.frame_count == config.sprites["idle"].frames
    win.close()
