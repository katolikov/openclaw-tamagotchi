"""Speech bubble widget — frameless, transparent, fades in/out, anchored above the pet."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

# Visual constants
PADDING_X = 10
PADDING_Y = 6
CORNER_RADIUS = 8
TAIL_HEIGHT = 8
TAIL_HALF_WIDTH = 6
SHADOW_OFFSET = 2
SHADOW_BLUR_LAYERS = 3  # cheap fake-blur by drawing several offset rects

# Timing (ms)
FADE_IN_MS = 180
FADE_OUT_MS = 320
DEFAULT_HOLD_MS = 3000

BUBBLE_BG = QColor(255, 255, 255, 240)
BUBBLE_BORDER = QColor(60, 60, 60, 220)
SHADOW_COLOR = QColor(0, 0, 0, 40)
TEXT_COLOR = QColor(30, 30, 30)
TEXT_FONT_FAMILY = "Helvetica"
TEXT_FONT_PT = 11

# Maximum bubble width (pixels) — text wraps beyond this.
MAX_BUBBLE_WIDTH = 280


class SpeechBubble(QWidget):
    """A small floating speech bubble. Call `say(text)` to display, then auto-fade out."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput  # never steals clicks
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._text = ""
        self._anchor: QPoint | None = None  # global pos of pet's top-center

        self._font = QFont(TEXT_FONT_FAMILY, TEXT_FONT_PT)
        self._font.setStyleHint(QFont.StyleHint.SansSerif)

        self.setWindowOpacity(0.0)

        self._anim_group: QSequentialAnimationGroup | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def say(self, text: str, *, hold_ms: int = DEFAULT_HOLD_MS) -> None:
        """Show `text` for ~hold_ms, fading in then out. Cancels any in-flight bubble."""
        self._text = text
        self._resize_for_text(text)
        self._reposition()
        self.show()
        self.raise_()
        self._start_fade(hold_ms)
        self.update()

    def set_anchor(self, global_top_center: QPoint) -> None:
        """Update the anchor (pet top-center, in global coords). Call when the pet moves."""
        self._anchor = global_top_center
        if self.isVisible():
            self._reposition()

    @property
    def text(self) -> str:
        return self._text

    # ------------------------------------------------------------------
    # Sizing & positioning
    # ------------------------------------------------------------------
    def _resize_for_text(self, text: str) -> None:
        fm = QFontMetrics(self._font)
        # Compute wrapped text size up to MAX_BUBBLE_WIDTH-2*PADDING_X.
        text_width_cap = MAX_BUBBLE_WIDTH - 2 * PADDING_X
        rect = fm.boundingRect(
            QRect(0, 0, text_width_cap, 10_000),
            int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft),
            text,
        )
        w = rect.width() + 2 * PADDING_X + 2 * SHADOW_BLUR_LAYERS
        h = rect.height() + 2 * PADDING_Y + TAIL_HEIGHT + 2 * SHADOW_BLUR_LAYERS
        # A small minimum to look bubbly even for short text.
        w = max(w, 60)
        self.resize(w, h)

    def _reposition(self) -> None:
        if self._anchor is None:
            return
        # Anchor = pet top-center, in global coords. Tail tip should land slightly above it.
        gap = 4  # px between tail tip and pet
        x = self._anchor.x() - self.width() // 2
        y = self._anchor.y() - self.height() - gap
        self.move(x, y)

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _start_fade(self, hold_ms: int) -> None:
        if self._anim_group is not None:
            self._anim_group.stop()
            self._anim_group.deleteLater()

        fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        fade_in.setDuration(FADE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        fade_out.setDuration(FADE_OUT_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addPause(hold_ms)
        group.addAnimation(fade_out)
        group.finished.connect(self.hide)
        group.start()
        self._anim_group = group

        # Safety: hide even if the animation gets interrupted.
        self._hide_timer.start(FADE_IN_MS + hold_ms + FADE_OUT_MS + 200)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt naming)
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Bubble body rect (excludes the tail at the bottom).
        body_w = self.width() - 2 * SHADOW_BLUR_LAYERS
        body_h = self.height() - TAIL_HEIGHT - 2 * SHADOW_BLUR_LAYERS
        body_x = SHADOW_BLUR_LAYERS
        body_y = SHADOW_BLUR_LAYERS

        # Cheap soft shadow: draw the same path several times offset, fading.
        for i in range(SHADOW_BLUR_LAYERS, 0, -1):
            shadow = QColor(SHADOW_COLOR)
            shadow.setAlpha(max(8, SHADOW_COLOR.alpha() // (i * 2)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(
                body_x + SHADOW_OFFSET + i,
                body_y + SHADOW_OFFSET + i,
                body_w,
                body_h,
                CORNER_RADIUS,
                CORNER_RADIUS,
            )

        # Bubble path: rounded rect + downward triangle tail.
        path = QPainterPath()
        path.addRoundedRect(body_x, body_y, body_w, body_h, CORNER_RADIUS, CORNER_RADIUS)
        # Tail in the bottom-center, pointing down.
        tail_cx = self.width() / 2.0
        tail_top_y = body_y + body_h
        tail_tip_y = tail_top_y + TAIL_HEIGHT
        path.moveTo(tail_cx - TAIL_HALF_WIDTH, tail_top_y)
        path.lineTo(tail_cx, tail_tip_y)
        path.lineTo(tail_cx + TAIL_HALF_WIDTH, tail_top_y)
        path.closeSubpath()

        painter.setPen(QPen(BUBBLE_BORDER, 1))
        painter.setBrush(BUBBLE_BG)
        painter.drawPath(path)

        # Text inside body.
        painter.setPen(TEXT_COLOR)
        painter.setFont(self._font)
        text_rect = QRect(
            body_x + PADDING_X,
            body_y + PADDING_Y,
            body_w - 2 * PADDING_X,
            body_h - 2 * PADDING_Y,
        )
        painter.drawText(
            text_rect,
            int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignCenter),
            self._text,
        )
