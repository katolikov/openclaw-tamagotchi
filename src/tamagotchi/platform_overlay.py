"""Platform-specific tweaks to make the pet behave as a true desktop overlay.

Cross-platform contract:

    hide_dock_icon()                — remove the app from the OS app-switcher / dock
    configure_overlay_window(widget) — keep widget on top across app switches,
                                       across virtual desktops / Spaces, and
                                       prevent it from stealing focus

Both functions are *best-effort*: they silently no-op when the required
platform extras aren't installed, and never raise.

Most of the focus-stealing fix is actually done at the Qt layer in
PetWindow / SpeechBubble (``Qt.WindowType.WindowDoesNotAcceptFocus`` +
``Qt.FocusPolicy.NoFocus``), which works on every platform Qt supports.
This module handles the *additional* OS-level quirks:

    macOS    Qt.Tool maps to NSPanel which auto-hides when the parent app
             deactivates → fix via setHidesOnDeactivate_(False) +
             NSStatusWindowLevel + can-join-all-spaces collection behavior.
    Windows  Already correct via WS_EX_TOPMOST + WS_EX_TOOLWINDOW. We
             additionally call SetWindowPos(HWND_TOPMOST) to re-assert
             topmost after any external z-order disruption.
    Linux    `_NET_WM_STATE_ABOVE` + skip-taskbar/skip-pager are honored
             by virtually every modern X11/Wayland window manager via the
             Qt.WindowStaysOnTopHint flag we already set; nothing extra
             needed here. (We still expose the function for symmetry and
             future-proofing.)
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def hide_dock_icon() -> bool:
    """Remove the running process from the OS app-switcher / dock if possible.

    Currently meaningful only on macOS (where Python apps default to showing
    a dock icon). Windows and Linux never show a dock entry for a Qt app
    that uses ``Qt.WindowType.Tool`` + ``WindowStaysOnTopHint``, so this is
    a no-op on those platforms.
    """
    if sys.platform == "darwin":
        return _hide_dock_icon_darwin()
    return False


def configure_overlay_window(widget: QWidget) -> bool:
    """Make `widget` behave as a true desktop overlay.

    Must be called *after* ``widget.show()`` so the underlying native window
    has been created. Returns True on success, False otherwise.
    """
    if sys.platform == "darwin":
        return _configure_overlay_darwin(widget)
    if sys.platform.startswith("win"):
        return _configure_overlay_windows(widget)
    if sys.platform.startswith("linux"):
        return _configure_overlay_linux(widget)
    return False


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------
_NS_APP_ACTIVATION_POLICY_ACCESSORY = 1
_NS_STATUS_WINDOW_LEVEL = 25  # above NSFloatingWindowLevel (3); just under menu-bar items
_NS_COLLECTION_BEHAVIOR_CAN_JOIN_ALL_SPACES = 1 << 0   # 1
_NS_COLLECTION_BEHAVIOR_STATIONARY = 1 << 4            # 16
_NS_COLLECTION_BEHAVIOR_IGNORES_CYCLE = 1 << 6         # 64
_NS_DESKTOP_PET_COLLECTION = (
    _NS_COLLECTION_BEHAVIOR_CAN_JOIN_ALL_SPACES
    | _NS_COLLECTION_BEHAVIOR_STATIONARY
    | _NS_COLLECTION_BEHAVIOR_IGNORES_CYCLE
)
# THE crucial bit for "show without stealing focus from the active app":
# without this flag a Qt.Tool window is created as a normal NSPanel, which
# activates the parent app whenever it's shown. With this flag the panel
# becomes "non-activating" and never causes app activation on show().
_NS_WINDOW_STYLE_MASK_NON_ACTIVATING_PANEL = 1 << 7    # 128


def _hide_dock_icon_darwin() -> bool:
    try:
        import AppKit  # type: ignore[import-untyped]
    except ImportError:
        return False
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(_NS_APP_ACTIVATION_POLICY_ACCESSORY)
    return True


def _configure_overlay_darwin(widget: QWidget) -> bool:
    # Skip when running under headless Qt platforms — there is no real
    # NSWindow to configure and dereferencing winId() can segfault.
    import os

    if os.environ.get("QT_QPA_PLATFORM", "").startswith("offscreen"):
        return False
    # Same caveat: a widget that has never been shown has no native NSWindow.
    if not _has_native_window(widget):
        return False

    try:
        import objc  # type: ignore[import-untyped]
    except ImportError:
        return False

    try:
        win_id = int(widget.winId())
    except (TypeError, ValueError):
        return False
    if win_id == 0:
        return False
    try:
        nsview = objc.objc_object(c_void_p=win_id)
        nswindow = nsview.window()
        if nswindow is None:
            return False
        # Float above ordinary windows.
        nswindow.setLevel_(_NS_STATUS_WINDOW_LEVEL)
        # Stay visible when another app is active.
        nswindow.setHidesOnDeactivate_(False)
        # Show on every Space; don't appear in cmd-tab cycling.
        nswindow.setCollectionBehavior_(_NS_DESKTOP_PET_COLLECTION)
        # THE bit that prevents the bubble's appearance from stealing keyboard
        # focus from whatever the user is typing in. Only meaningful on NSPanel
        # (which Qt.Tool produces). On a plain NSWindow, setStyleMask_ may
        # raise — that's caught by the broad except below.
        try:
            current_mask = nswindow.styleMask()
            nswindow.setStyleMask_(
                current_mask | _NS_WINDOW_STYLE_MASK_NON_ACTIVATING_PANEL
            )
        except Exception:  # noqa: BLE001
            pass
        # NSPanel-only: don't become the key window unless absolutely needed.
        if hasattr(nswindow, "setBecomesKeyOnlyIfNeeded_"):
            try:
                nswindow.setBecomesKeyOnlyIfNeeded_(True)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001 — never crash the app over polish
        return False
    return True


def _has_native_window(widget: QWidget) -> bool:
    """Return True if `widget` has been shown at least once (native window exists)."""
    if widget.isVisible():
        return True
    # Non-public Qt attribute; check via the public testAttribute API.
    from PySide6.QtCore import Qt

    return widget.testAttribute(Qt.WidgetAttribute.WA_WState_Created)


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------
# SetWindowPos flags
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040


def _configure_overlay_windows(widget: QWidget) -> bool:
    """Re-assert HWND_TOPMOST so the pet stays above all other windows."""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return False
    win_id = widget.winId()
    if win_id is None:
        return False
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        SetWindowPos = user32.SetWindowPos  # noqa: N806
        SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        SetWindowPos.restype = wintypes.BOOL
        SetWindowPos(
            wintypes.HWND(int(win_id)),
            wintypes.HWND(_HWND_TOPMOST),
            0,
            0,
            0,
            0,
            _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE | _SWP_SHOWWINDOW,
        )
    except (OSError, AttributeError):
        return False
    return True


# ---------------------------------------------------------------------------
# Linux (X11 / Wayland)
# ---------------------------------------------------------------------------
def _configure_overlay_linux(_widget: QWidget) -> bool:
    """No-op on Linux.

    The Qt window flags (`WindowStaysOnTopHint`, `Tool`) already produce the
    correct ``_NET_WM_STATE_ABOVE`` + ``_NET_WM_WINDOW_TYPE_UTILITY`` hints
    that every modern Linux window manager honors. Wayland compositors that
    don't honor these hints (rare) won't be reachable from a regular client
    anyway, so there's nothing platform-specific to do here.
    """
    return True
