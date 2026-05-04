"""Tests for SpeechBubble widget basic behavior."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from tamagotchi.speech_bubble import SpeechBubble


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


def test_say_sets_text_and_resizes(qapp: QApplication) -> None:
    bubble = SpeechBubble()
    bubble.set_anchor(QPoint(500, 500))
    bubble.say("Hello, world!", hold_ms=10)
    assert bubble.text == "Hello, world!"
    assert bubble.width() > 0
    assert bubble.height() > 0
    bubble.hide()


def test_anchor_positions_above_target(qapp: QApplication) -> None:
    bubble = SpeechBubble()
    bubble.set_anchor(QPoint(800, 600))
    bubble.say("Test", hold_ms=10)
    # Bubble bottom should be a few px above the anchor Y.
    assert bubble.y() + bubble.height() <= 600
    # Horizontally centered around the anchor x.
    bubble_center = bubble.x() + bubble.width() // 2
    assert abs(bubble_center - 800) <= 1
    bubble.hide()


def test_long_text_wraps_within_max_width(qapp: QApplication) -> None:
    bubble = SpeechBubble()
    bubble.set_anchor(QPoint(0, 0))
    long_text = "This is a fairly long phrase that should wrap when it exceeds the cap. " * 3
    bubble.say(long_text, hold_ms=10)
    # Width must not exceed the cap (plus shadow padding allowance).
    from tamagotchi.speech_bubble import MAX_BUBBLE_WIDTH

    assert bubble.width() <= MAX_BUBBLE_WIDTH + 20
    bubble.hide()


def test_starts_hidden_until_say(qapp: QApplication) -> None:
    bubble = SpeechBubble()
    assert not bubble.isVisible()
    bubble.set_anchor(QPoint(100, 100))
    bubble.say("hi", hold_ms=10)
    assert bubble.isVisible()
    bubble.hide()
