"""Tests for PetWindow drag-to-move logic."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from tamagotchi.config import load_pet_config
from tamagotchi.window import PetWindow

PETS_DIR = Path(__file__).resolve().parent.parent / "pets"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


def _press(global_pos: QPoint) -> QMouseEvent:
    local = QPointF(0, 0)
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        local,
        QPointF(global_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _move(global_pos: QPoint) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(0, 0),
        QPointF(global_pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _release(global_pos: QPoint) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(0, 0),
        QPointF(global_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_drag_moves_window(qapp: QApplication) -> None:
    pet_dir = PETS_DIR / "claw"
    config = load_pet_config(pet_dir)
    win = PetWindow(pet_dir=pet_dir, config=config)
    win.move(100, 100)

    # Press at global (110, 110) — 10 px into the window.
    win.mousePressEvent(_press(QPoint(110, 110)))
    assert win._drag_offset is not None

    # Drag to (200, 150). Window should follow: 200-10=190, 150-10=140.
    win.mouseMoveEvent(_move(QPoint(200, 150)))
    assert win.x() == 190
    assert win.y() == 140

    # Release clears state.
    win.mouseReleaseEvent(_release(QPoint(200, 150)))
    assert win._drag_offset is None

    win.close()


def test_click_emits_clicked_signal(qapp: QApplication) -> None:
    pet_dir = PETS_DIR / "claw"
    config = load_pet_config(pet_dir)
    win = PetWindow(pet_dir=pet_dir, config=config)
    win.move(0, 0)

    received: list[None] = []
    win.clicked.connect(lambda: received.append(None))

    # Press and release at the same global pos == click.
    win.mousePressEvent(_press(QPoint(20, 20)))
    win.mouseReleaseEvent(_release(QPoint(20, 20)))
    assert len(received) == 1

    win.close()


def test_drag_does_not_emit_clicked(qapp: QApplication) -> None:
    pet_dir = PETS_DIR / "claw"
    config = load_pet_config(pet_dir)
    win = PetWindow(pet_dir=pet_dir, config=config)
    win.move(0, 0)

    received: list[None] = []
    win.clicked.connect(lambda: received.append(None))

    win.mousePressEvent(_press(QPoint(20, 20)))
    win.mouseMoveEvent(_move(QPoint(100, 100)))  # well past threshold
    win.mouseReleaseEvent(_release(QPoint(100, 100)))
    assert received == []

    win.close()
