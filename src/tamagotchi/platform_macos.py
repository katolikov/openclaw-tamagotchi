"""macOS-specific niceties. Best-effort: silent on import errors / non-darwin systems."""

from __future__ import annotations

import sys


def hide_dock_icon() -> bool:
    """Switch this process to a 'Accessory' app on macOS so it has no dock icon.

    Returns True on success, False otherwise. Requires `pyobjc-framework-Cocoa`
    to be installed (`pip install -e .[macos]`). On non-darwin platforms or
    when PyObjC is unavailable, returns False without raising.
    """
    if sys.platform != "darwin":
        return False
    try:
        import AppKit  # type: ignore[import-not-found]
    except ImportError:
        return False
    # AppKit constant: NSApplicationActivationPolicyAccessory == 1
    accessory_policy = 1
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(accessory_policy)
    return True
