"""Generate placeholder pixel-art sprites and the tray icon.

Run once after install:

    python scripts/generate_placeholders.py

The result is committed to the repo so end users don't need to re-run it.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPRITES_DIR = ROOT / "pets" / "claw" / "sprites"
TRAY_PATH = ROOT / "assets" / "tray_icon.png"

# ---- Palette (RGBA) ---------------------------------------------------------
TRANSPARENT = (0, 0, 0, 0)
BODY = (255, 178, 102, 255)       # warm orange
BODY_DARK = (204, 122, 51, 255)   # shadow
EAR_INNER = (255, 102, 178, 255)  # pink
EYE = (40, 30, 30, 255)           # near-black
WHITE = (250, 250, 250, 255)
MOUTH = (180, 40, 60, 255)        # mouth/nose

PALETTE: dict[str, tuple[int, int, int, int]] = {
    " ": TRANSPARENT,
    "B": BODY,
    "D": BODY_DARK,
    "P": EAR_INNER,
    "E": EYE,
    "W": WHITE,
    "M": MOUTH,
}

FRAME_SIZE = 32  # all frames are 32x32

# ---- Frame templates --------------------------------------------------------
# Open eyes, mouth closed.
_OPEN_EYES = [
    "                                ",
    "                                ",
    "      DD              DD        ",
    "     DPPD            DPPD       ",
    "    DPPPPD          DPPPPD      ",
    "    DPPPPPDDDDDDDDDDPPPPPD      ",
    "    DPPPPPDBBBBBBBBDPPPPPD      ",
    "     DPPPDBBBBBBBBBBDPPPD       ",
    "      DDDBBBBBBBBBBBBDDD        ",
    "        BBBBBBBBBBBBBBBB        ",
    "       BBBBBBBBBBBBBBBBBB       ",
    "      BBBWWBBBBBBBBBBWWBB       ",
    "      BBBWEBBBBBBBBBBWEBB       ",
    "      BBBWWBBBBBBBBBBWWBB       ",
    "       BBBBBBBMMMMBBBBBBB       ",
    "       BBBBBBBMMMMBBBBBBB       ",
    "        BBBBBBBBBBBBBBBB        ",
    "        BBBBBBBBBBBBBBBB        ",
    "         BBBBBBBBBBBBBB         ",
    "         BBBBBBBBBBBBBB         ",
    "         BBBBBBBBBBBBBB         ",
    "         BBBBBBBBBBBBBB         ",
    "         BB BBBB  BB BB         ",
    "         BB BBBB  BB BB         ",
    "          DDD DD  DD            ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
]

# Closed eyes: replace the 3-row eye block (rows 11-13) with a flat closed line.
_CLOSED_EYES = list(_OPEN_EYES)
_CLOSED_EYES[11] = "      BBBBBBBBBBBBBBBBBBBB      "
_CLOSED_EYES[12] = "      BBBEEBBBBBBBBBBEEBB       "
_CLOSED_EYES[13] = "      BBBBBBBBBBBBBBBBBBBB      "


def _shift_down(rows: list[str], n: int = 1) -> list[str]:
    """Shift all non-blank rows downward by n; pad top with blank rows."""
    if n <= 0:
        return list(rows)
    blank = " " * FRAME_SIZE
    return [blank] * n + rows[: FRAME_SIZE - n]


# 8-frame breathing/blink loop. Subtle 1px vertical bob + a single blink.
IDLE_FRAMES: list[list[str]] = [
    _OPEN_EYES,                  # 0
    _OPEN_EYES,                  # 1
    _shift_down(_OPEN_EYES, 1),  # 2 — exhale (down 1px)
    _shift_down(_OPEN_EYES, 1),  # 3
    _OPEN_EYES,                  # 4 — inhale
    _OPEN_EYES,                  # 5
    _CLOSED_EYES,                # 6 — blink
    _OPEN_EYES,                  # 7
]


def _shift_horiz(rows: list[str], n: int) -> list[str]:
    """Shift content horizontally by n columns (positive=right). Pads with blanks."""
    if n == 0:
        return list(rows)
    if n > 0:
        return [(" " * n + row)[:FRAME_SIZE] for row in rows]
    # n < 0: shift left
    n = -n
    return [(row[n:] + " " * n)[:FRAME_SIZE] for row in rows]


# 6-frame walk cycle. The pet bobs up/down and sways subtly side-to-side; the
# real horizontal motion comes from translating the window each tick.
WALK_FRAMES: list[list[str]] = [
    _OPEN_EYES,                                       # 0 neutral
    _shift_horiz(_OPEN_EYES, 1),                      # 1 sway right
    _shift_down(_OPEN_EYES, 1),                       # 2 step down
    _shift_horiz(_OPEN_EYES, -1),                     # 3 sway left
    _OPEN_EYES,                                       # 4 neutral
    _shift_down(_shift_horiz(_OPEN_EYES, 1), 1),      # 5 step down + right
]

# 4-frame sleep cycle. Eyes closed, body settled lower, slow rise/fall.
SLEEP_FRAMES: list[list[str]] = [
    _shift_down(_CLOSED_EYES, 2),
    _shift_down(_CLOSED_EYES, 2),
    _shift_down(_CLOSED_EYES, 3),
    _shift_down(_CLOSED_EYES, 3),
]

# ---- Tray icon --------------------------------------------------------------
_TRAY_PIXELS = [
    "                ",
    "  DD        DD  ",
    " DPPD      DPPD ",
    " DPPDDDDDDDPPD  ",
    "  DBBBBBBBBBBD  ",
    "  BWBBBBBBBBWB  ",
    "  BWBBBBBBBBWB  ",
    "  BBBBBMMBBBBB  ",
    "  BBBBBMMBBBBB  ",
    "  BBBBBBBBBBBB  ",
    "   BBBBBBBBBB   ",
    "    BBBBBBBB    ",
    "    BB BB BB    ",
    "    DD DD DD    ",
    "                ",
    "                ",
]


# ---- Rendering --------------------------------------------------------------
def render_frame(pixels: list[str]) -> Image.Image:
    h = len(pixels)
    w = max(len(row) for row in pixels)
    img = Image.new("RGBA", (w, h), TRANSPARENT)
    px = img.load()
    assert px is not None
    for y, row in enumerate(pixels):
        for x, ch in enumerate(row.ljust(w)):
            px[x, y] = PALETTE.get(ch, TRANSPARENT)
    return img


def render_sheet(frames: list[list[str]]) -> Image.Image:
    """Compose frames horizontally into a sprite sheet."""
    rendered = [render_frame(f) for f in frames]
    h = max(img.height for img in rendered)
    w = sum(img.width for img in rendered)
    sheet = Image.new("RGBA", (w, h), TRANSPARENT)
    x = 0
    for img in rendered:
        sheet.paste(img, (x, 0))
        x += img.width
    return sheet


def main() -> None:
    SPRITES_DIR.mkdir(parents=True, exist_ok=True)
    TRAY_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Single-frame placeholder kept for backwards-compat with Phase 1 callers.
    placeholder = render_frame(_OPEN_EYES)
    placeholder_path = SPRITES_DIR / "placeholder.png"
    placeholder.save(placeholder_path)
    print(f"wrote {placeholder_path} ({placeholder.size[0]}x{placeholder.size[1]})")

    # Idle animation sprite sheet (Phase 2).
    idle = render_sheet(IDLE_FRAMES)
    idle_path = SPRITES_DIR / "idle.png"
    idle.save(idle_path)
    print(f"wrote {idle_path} ({idle.size[0]}x{idle.size[1]}, {len(IDLE_FRAMES)} frames)")

    # Walk animation (Phase 4).
    walk = render_sheet(WALK_FRAMES)
    walk_path = SPRITES_DIR / "walk.png"
    walk.save(walk_path)
    print(f"wrote {walk_path} ({walk.size[0]}x{walk.size[1]}, {len(WALK_FRAMES)} frames)")

    # Sleep animation (Phase 4).
    sleep = render_sheet(SLEEP_FRAMES)
    sleep_path = SPRITES_DIR / "sleep.png"
    sleep.save(sleep_path)
    print(f"wrote {sleep_path} ({sleep.size[0]}x{sleep.size[1]}, {len(SLEEP_FRAMES)} frames)")

    # Tray icon (scaled 2x for crispness in hi-dpi tray bars).
    tray = render_frame(_TRAY_PIXELS)
    tray = tray.resize((tray.size[0] * 2, tray.size[1] * 2), Image.NEAREST)
    tray.save(TRAY_PATH)
    print(f"wrote {TRAY_PATH} ({tray.size[0]}x{tray.size[1]})")


if __name__ == "__main__":
    main()
