"""Tests for SpriteSheet slicing and AnimationPlayer frame advancement."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from tamagotchi.animation import AnimationPlayer, SpriteSheet, SpriteSheetError

SPRITES_DIR = Path(__file__).resolve().parent.parent / "pets" / "claw" / "sprites"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


def _make_sheet(width: int, height: int) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill()  # solid white; contents don't matter for slicing tests
    return pix


def test_sheet_slices_evenly(qapp: QApplication) -> None:
    sheet = SpriteSheet(_make_sheet(80, 16), frames=5)
    assert sheet.frame_count == 5
    assert sheet.frame_size == (16, 16)
    f = sheet.frame(0)
    assert f.width() == 16 and f.height() == 16


def test_sheet_rejects_uneven_division(qapp: QApplication) -> None:
    with pytest.raises(SpriteSheetError):
        SpriteSheet(_make_sheet(81, 16), frames=5)


def test_sheet_rejects_zero_frames(qapp: QApplication) -> None:
    with pytest.raises(SpriteSheetError):
        SpriteSheet(_make_sheet(80, 16), frames=0)


def test_frame_index_out_of_range(qapp: QApplication) -> None:
    sheet = SpriteSheet(_make_sheet(80, 16), frames=5)
    with pytest.raises(IndexError):
        sheet.frame(5)


def test_player_loops(qapp: QApplication) -> None:
    sheet = SpriteSheet(_make_sheet(80, 16), frames=4)
    player = AnimationPlayer(sheet, fps=60, loop=True)
    assert player.index == 0
    player.advance()
    assert player.index == 1
    player.advance()
    player.advance()
    assert player.index == 3
    player.advance()  # wraps
    assert player.index == 0
    assert not player.finished


def test_player_non_looping_stops_at_last(qapp: QApplication) -> None:
    sheet = SpriteSheet(_make_sheet(48, 16), frames=3)
    player = AnimationPlayer(sheet, fps=60, loop=False)
    for _ in range(10):
        player.advance()
    assert player.index == 2
    assert player.finished


def test_player_reset(qapp: QApplication) -> None:
    sheet = SpriteSheet(_make_sheet(48, 16), frames=3)
    player = AnimationPlayer(sheet, fps=60, loop=False)
    player.advance()
    player.advance()
    player.advance()
    assert player.finished
    player.reset()
    assert player.index == 0
    assert not player.finished


def test_invalid_fps_rejected(qapp: QApplication) -> None:
    sheet = SpriteSheet(_make_sheet(48, 16), frames=3)
    with pytest.raises(ValueError):
        AnimationPlayer(sheet, fps=0)


def test_load_real_idle_sheet(qapp: QApplication) -> None:
    """Sanity check the actual generated idle.png slices into the expected count."""
    path = SPRITES_DIR / "idle.png"
    assert path.is_file(), f"missing generated asset: {path}"
    sheet = SpriteSheet.load(path, frames=8)
    assert sheet.frame_count == 8
    fw, fh = sheet.frame_size
    assert fw == 32 and fh == 32
