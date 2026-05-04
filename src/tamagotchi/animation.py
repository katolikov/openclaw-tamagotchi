"""Sprite-sheet animation: slice horizontal strips and play them on a QTimer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap


class SpriteSheetError(ValueError):
    """Raised when a sprite sheet cannot be sliced cleanly."""


class SpriteSheet:
    """A horizontal-strip sprite sheet, sliced into N equal-width frames."""

    def __init__(self, pixmap: QPixmap, frames: int) -> None:
        if pixmap.isNull():
            raise SpriteSheetError("sprite sheet pixmap is null (failed to load?)")
        if frames <= 0:
            raise SpriteSheetError(f"frames must be >= 1, got {frames}")
        if pixmap.width() % frames != 0:
            raise SpriteSheetError(
                f"sheet width {pixmap.width()} is not divisible by frames={frames}"
            )
        self._sheet = pixmap
        self._frames = frames
        self._frame_w = pixmap.width() // frames
        self._frame_h = pixmap.height()

    @classmethod
    def load(cls, path: Path, frames: int) -> SpriteSheet:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise SpriteSheetError(f"failed to load sprite sheet: {path}")
        return cls(pixmap, frames=frames)

    @property
    def frame_count(self) -> int:
        return self._frames

    @property
    def frame_size(self) -> tuple[int, int]:
        return self._frame_w, self._frame_h

    def frame(self, index: int) -> QPixmap:
        if not 0 <= index < self._frames:
            raise IndexError(f"frame index {index} out of range [0, {self._frames})")
        return self._sheet.copy(
            index * self._frame_w, 0, self._frame_w, self._frame_h
        )

    def scaled_frame(self, index: int, scale: int) -> QPixmap:
        """Return frame `index` scaled by integer factor (nearest-neighbor)."""
        f = self.frame(index)
        if scale == 1:
            return f
        return f.scaled(
            f.width() * scale,
            f.height() * scale,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    def flipped_horizontally(self) -> SpriteSheet:
        """Return a new SpriteSheet whose frames are mirrored left-to-right."""
        from PySide6.QtGui import QImage, QPainter, QTransform

        flipped_image = QImage(
            self._sheet.width(), self._sheet.height(), QImage.Format.Format_ARGB32
        )
        flipped_image.fill(0)
        painter = QPainter(flipped_image)
        for i in range(self._frames):
            mirrored = self.frame(i).transformed(QTransform().scale(-1, 1))
            painter.drawPixmap(i * self._frame_w, 0, mirrored)
        painter.end()
        return SpriteSheet(QPixmap.fromImage(flipped_image), frames=self._frames)


class AnimationPlayer(QObject):
    """Plays a SpriteSheet at a fixed FPS, emitting `frame_changed` each tick.

    Designed to be testable without a real event loop: `advance()` mutates state
    deterministically; the QTimer just calls `advance()` periodically.
    """

    frame_changed = Signal(int)  # emits new frame index

    def __init__(
        self,
        sheet: SpriteSheet,
        *,
        fps: float = 6.0,
        loop: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if fps <= 0:
            raise ValueError(f"fps must be > 0, got {fps}")
        self._sheet = sheet
        self._fps = fps
        self._loop = loop
        self._index = 0
        self._finished = False

        self._timer = QTimer(self)
        # CoarseTimer keeps CPU low; pet animation doesn't need ms-accurate timing.
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.setInterval(int(round(1000.0 / fps)))
        self._timer.timeout.connect(self.advance)

    @property
    def index(self) -> int:
        return self._index

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def sheet(self) -> SpriteSheet:
        return self._sheet

    def current_pixmap(self, scale: int = 1) -> QPixmap:
        return self._sheet.scaled_frame(self._index, scale)

    def start(self) -> None:
        self._finished = False
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self._index = 0
        self._finished = False
        self.frame_changed.emit(self._index)

    def advance(self) -> None:
        """Move to the next frame (or stop, for non-looping animations)."""
        if self._finished:
            return
        next_index = self._index + 1
        if next_index >= self._sheet.frame_count:
            if self._loop:
                self._index = 0
            else:
                self._index = self._sheet.frame_count - 1
                self._finished = True
                self._timer.stop()
                self.frame_changed.emit(self._index)
                return
        else:
            self._index = next_index
        self.frame_changed.emit(self._index)


def connect_to_label_setter(
    player: AnimationPlayer,
    setter: Callable[[QPixmap], None],
    *,
    scale: int = 1,
) -> None:
    """Convenience: forward each frame change to a pixmap setter (e.g., QLabel.setPixmap)."""

    def _on_change(_index: int) -> None:
        setter(player.current_pixmap(scale=scale))

    player.frame_changed.connect(_on_change)
    setter(player.current_pixmap(scale=scale))  # paint initial frame immediately
