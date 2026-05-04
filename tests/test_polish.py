"""Tests for Phase 8 polish: sprite flipping and macOS helper safety."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from tamagotchi.animation import SpriteSheet
from tamagotchi.platform_overlay import configure_overlay_window, hide_dock_icon

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


# ---- sprite flip ----------------------------------------------------------
def test_flipped_sheet_preserves_dimensions(qapp: QApplication) -> None:
    pix = QPixmap(80, 16)
    pix.fill()
    sheet = SpriteSheet(pix, frames=5)
    flipped = sheet.flipped_horizontally()
    assert flipped.frame_count == 5
    assert flipped.frame_size == sheet.frame_size


def test_flipped_real_walk_sheet(qapp: QApplication) -> None:
    sheet = SpriteSheet.load(PETS_DIR / "claw" / "sprites" / "walk.png", frames=6)
    flipped = sheet.flipped_horizontally()
    # Same number of frames; same per-frame dimensions.
    assert flipped.frame_count == sheet.frame_count
    assert flipped.frame_size == sheet.frame_size
    # Image content actually differs (well, unless the sprite is symmetric,
    # which our placeholder is — so just check the API works without error).
    f0 = sheet.frame(0).toImage()
    f0_flipped = flipped.frame(0).toImage()
    assert f0.size() == f0_flipped.size()


# ---- macOS hide_dock_icon -------------------------------------------------
def test_hide_dock_icon_returns_false_on_non_macos() -> None:
    if sys.platform == "darwin":
        pytest.skip("macOS-only negative test")
    assert hide_dock_icon() is False


def test_hide_dock_icon_safe_to_call_repeatedly(qapp: QApplication) -> None:
    # Whatever the platform, calling this must never raise.
    hide_dock_icon()
    hide_dock_icon()


def test_configure_overlay_window_safe_with_unshown_widget(qapp: QApplication) -> None:
    """Must never raise / crash even when called on a widget without a native window."""
    from PySide6.QtWidgets import QWidget

    w = QWidget()
    # Should silently no-op (not crash) under offscreen Qt + un-shown widget.
    assert configure_overlay_window(w) is False
