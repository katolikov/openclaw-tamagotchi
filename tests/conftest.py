"""Pytest config: force Qt to use the offscreen platform so tests are headless-safe."""

from __future__ import annotations

import os

# Must be set before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
