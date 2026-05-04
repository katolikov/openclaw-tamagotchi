"""Transparent, frameless, always-on-top window that hosts the animated pet sprite."""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from tamagotchi.animation import (
    AnimationPlayer,
    SpriteSheet,
    SpriteSheetError,
    connect_to_label_setter,
)
from tamagotchi.config import PetConfig, resolve_sprite_path

DEFAULT_SCALE = 2  # pixel-art look: nearest-neighbor 2x

# A press-release within this distance counts as a click rather than a drag.
CLICK_DRAG_THRESHOLD_PX = 4


class PetWindow(QWidget):
    """A frameless, transparent, always-on-top window showing the animated pet."""

    clicked = Signal()  # emitted on a non-drag left-click on the sprite

    def __init__(
        self,
        pet_dir: Path,
        config: PetConfig,
        *,
        scale: int = DEFAULT_SCALE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pet_dir = pet_dir
        self.config = config
        self._scale = scale

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar entry
            | Qt.WindowType.WindowDoesNotAcceptFocus  # never steal keyboard focus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # Belt-and-braces at the QWidget level so clicks on the pet never pull
        # focus away from text fields the user is typing in.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle(config.name)

        self._label = QLabel(self)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._player: AnimationPlayer | None = None
        # Drag state: offset from the window top-left to the press point.
        self._drag_offset: QPoint | None = None
        # Track press position to distinguish click from drag.
        self._press_global_pos: QPoint | None = None
        self._has_moved_since_press = False

        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._init_animation()

    # ------------------------------------------------------------------
    # Animation setup
    # ------------------------------------------------------------------
    def _init_animation(self) -> None:
        idle = self.config.sprites["idle"]  # validator guarantees presence
        sheet_path = resolve_sprite_path(self.pet_dir, idle)
        try:
            sheet = SpriteSheet.load(sheet_path, frames=idle.frames)
        except SpriteSheetError:
            self._show_fallback()
            return
        self.set_animation(sheet, fps=idle.fps, loop=idle.loop)

    def set_animation(self, sheet: SpriteSheet, *, fps: float, loop: bool) -> None:
        """Replace the running animation. Resizes the window to fit the new sheet."""
        fw, fh = sheet.frame_size
        size = (fw * self._scale, fh * self._scale)
        self._label.resize(*size)
        self.resize(*size)

        if self._player is not None:
            self._player.stop()
            self._player.deleteLater()

        self._player = AnimationPlayer(sheet, fps=fps, loop=loop, parent=self)
        connect_to_label_setter(self._player, self._label.setPixmap, scale=self._scale)
        self._player.start()

    @property
    def player(self) -> AnimationPlayer | None:
        return self._player

    def _show_fallback(self) -> None:
        """If the sprite sheet is missing, show a magenta square so something is visible."""
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.magenta)
        self._label.setPixmap(pix)
        self._label.resize(size, size)
        self.resize(size, size)

    # ------------------------------------------------------------------
    # Spawn placement
    # ------------------------------------------------------------------
    def spawn_at_random_bottom(self, *, margin_px: int = 20) -> None:
        """Place the pet at a random horizontal position along the bottom of the active screen.

        The "active" screen is the one under the cursor when launched, falling back
        to the primary screen on headless systems.
        """
        from PySide6.QtGui import QCursor, QGuiApplication

        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x_min = geo.left() + margin_px
        x_max = max(x_min, geo.right() - self.width() - margin_px)
        x = random.randint(x_min, x_max) if x_max > x_min else x_min
        y = geo.bottom() - self.height() - margin_px
        self.move(x, y)

    # ------------------------------------------------------------------
    # Drag-to-move support (frameless windows don't get this for free).
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            press_global = event.globalPosition().toPoint()
            self._drag_offset = press_global - self.frameGeometry().topLeft()
            self._press_global_pos = press_global
            self._has_moved_since_press = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            current = event.globalPosition().toPoint()
            if self._press_global_pos is not None:
                delta = current - self._press_global_pos
                if abs(delta.x()) + abs(delta.y()) > CLICK_DRAG_THRESHOLD_PX:
                    self._has_moved_since_press = True
            new_top_left = current - self._drag_offset
            self.move(new_top_left)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            was_click = not self._has_moved_since_press
            self._drag_offset = None
            self._press_global_pos = None
            self._has_moved_since_press = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if was_click:
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: object) -> None:  # noqa: N802 (Qt naming)
        if self._player is not None:
            self._player.stop()
        super().closeEvent(event)  # type: ignore[arg-type]
