"""Generate placeholder pixel-art sprites for every bundled pet, plus the tray icon.

Run once after edits:

    python scripts/generate_placeholders.py

The result is committed to the repo so end users don't need to re-run it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PETS_ROOT = ROOT / "pets"
TRAY_PATH = ROOT / "assets" / "tray_icon.png"

FRAME_SIZE = 32  # all frames are 32x32


# =============================================================================
# Palettes (per-pet)
# =============================================================================
TRANSPARENT = (0, 0, 0, 0)


def _palette_claw() -> dict[str, tuple[int, int, int, int]]:
    return {
        " ": TRANSPARENT,
        "B": (255, 178, 102, 255),  # warm orange body
        "D": (204, 122, 51, 255),   # body shadow
        "P": (255, 102, 178, 255),  # pink ear
        "E": (40, 30, 30, 255),     # eye
        "W": (250, 250, 250, 255),  # eye-white
        "M": (180, 40, 60, 255),    # mouth/nose
    }


def _palette_rabbit() -> dict[str, tuple[int, int, int, int]]:
    # Mochi — agouti brown lop-ear bunny.
    return {
        " ": TRANSPARENT,
        "F": (139, 90, 50, 255),    # warm sepia brown fur
        "G": (90, 55, 30, 255),     # darker brown shadow
        "P": (220, 130, 140, 255),  # pink nose
        "E": (30, 20, 15, 255),     # eye
        "W": (240, 230, 220, 255),  # cream muzzle patch
        "M": (210, 80, 110, 255),   # unused (kept for renderer compatibility)
    }


def _palette_dachshund() -> dict[str, tuple[int, int, int, int]]:
    # Frank — classic black-and-tan dachshund.
    return {
        " ": TRANSPARENT,
        "K": (35, 28, 25, 255),     # near-black body
        "L": (10, 8, 6, 255),       # outline / shadow / nose
        "T": (175, 100, 45, 255),   # rust-tan markings
        "E": (10, 8, 6, 255),       # eye
        "W": (210, 160, 100, 255),  # lighter tan highlight
        "M": (10, 8, 6, 255),       # nose (same as L)
    }


# =============================================================================
# Helpers shared across pets
# =============================================================================
def _shift_down(rows: list[str], n: int = 1) -> list[str]:
    if n <= 0:
        return list(rows)
    blank = " " * FRAME_SIZE
    return [blank] * n + rows[: FRAME_SIZE - n]


def _shift_horiz(rows: list[str], n: int) -> list[str]:
    if n == 0:
        return list(rows)
    if n > 0:
        return [(" " * n + row)[:FRAME_SIZE] for row in rows]
    n = -n
    return [(row[n:] + " " * n)[:FRAME_SIZE] for row in rows]


def _replace(rows: list[str], **mapping: str) -> list[str]:
    """Apply a char-mapping to every row (e.g. swap 'B' for 'F')."""
    out = []
    for row in rows:
        for src, dst in mapping.items():
            row = row.replace(src, dst)
        out.append(row)
    return out


# =============================================================================
# Pet definitions
# =============================================================================
@dataclass
class PetSpriteSet:
    name: str
    palette: dict[str, tuple[int, int, int, int]]
    idle_frames: list[list[str]]
    walk_frames: list[list[str]]
    sleep_frames: list[list[str]]
    placeholder: list[str] = field(default_factory=list)


# ---- CLAW (orange pirate cat) -----------------------------------------------
_CLAW_OPEN_EYES = [
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
_CLAW_CLOSED_EYES = list(_CLAW_OPEN_EYES)
_CLAW_CLOSED_EYES[11] = "      BBBBBBBBBBBBBBBBBBBB      "
_CLAW_CLOSED_EYES[12] = "      BBBEEBBBBBBBBBBEEBB       "
_CLAW_CLOSED_EYES[13] = "      BBBBBBBBBBBBBBBBBBBB      "

CLAW = PetSpriteSet(
    name="claw",
    palette=_palette_claw(),
    idle_frames=[
        _CLAW_OPEN_EYES,
        _CLAW_OPEN_EYES,
        _shift_down(_CLAW_OPEN_EYES, 1),
        _shift_down(_CLAW_OPEN_EYES, 1),
        _CLAW_OPEN_EYES,
        _CLAW_OPEN_EYES,
        _CLAW_CLOSED_EYES,
        _CLAW_OPEN_EYES,
    ],
    walk_frames=[
        _CLAW_OPEN_EYES,
        _shift_horiz(_CLAW_OPEN_EYES, 1),
        _shift_down(_CLAW_OPEN_EYES, 1),
        _shift_horiz(_CLAW_OPEN_EYES, -1),
        _CLAW_OPEN_EYES,
        _shift_down(_shift_horiz(_CLAW_OPEN_EYES, 1), 1),
    ],
    sleep_frames=[
        _shift_down(_CLAW_CLOSED_EYES, 2),
        _shift_down(_CLAW_CLOSED_EYES, 2),
        _shift_down(_CLAW_CLOSED_EYES, 3),
        _shift_down(_CLAW_CLOSED_EYES, 3),
    ],
    placeholder=_CLAW_OPEN_EYES,
)


# ---- SHAMIL (upright-eared brown bunny) -------------------------------------
# Two tall pointy ears reading unmistakably as rabbit; round head, pink nose,
# cream muzzle patch, compact body, two split front feet.
_RABBIT_OPEN_EYES = [
    "                                ",
    "                                ",
    "          FFFF    FFFF          ",
    "          FPPF    FPPF          ",
    "          FPPF    FPPF          ",
    "          FPPF    FPPF          ",
    "          FFFF    FFFF          ",
    "          FFFFFFFFFFFF          ",
    "        FFFFFFFFFFFFFFFF        ",
    "       FFFFFFFFFFFFFFFFFF       ",
    "      FFFFFFFFFFFFFFFFFFFF      ",
    "      FFFFEEFFFFFFFFEEFFFF      ",
    "      FFFFEEFFFFFFFFEEFFFF      ",
    "      FFFFFFFFFFFFFFFFFFFF      ",
    "      FFFFFFFFPPPPFFFFFFFF      ",
    "      FFFFFFFWWWWWWFFFFFFF      ",
    "       FFFFFFFFFFFFFFFFFF       ",
    "      FFFFFFFFFFFFFFFFFFFF      ",
    "      FFFFFFFFFFFFFFFFFFFF      ",
    "      FFFFFFFFFFFFFFFFFFFF      ",
    "       FFFFFFFFFFFFFFFFFF       ",
    "        FFFFFFFFFFFFFFFF        ",
    "        FFFF        FFFF        ",
    "        FFFF        FFFF        ",
    "        GGGG        GGGG        ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
]
_RABBIT_CLOSED_EYES = list(_RABBIT_OPEN_EYES)
_RABBIT_CLOSED_EYES[11] = "      FFFFFFFFFFFFFFFFFFFF      "
_RABBIT_CLOSED_EYES[12] = "      FFFFEEFFFFFFFFEEFFFF      "

RABBIT = PetSpriteSet(
    name="rabbit",
    palette=_palette_rabbit(),
    idle_frames=[
        _RABBIT_OPEN_EYES,
        _RABBIT_OPEN_EYES,
        _shift_down(_RABBIT_OPEN_EYES, 1),
        _shift_down(_RABBIT_OPEN_EYES, 1),
        _RABBIT_OPEN_EYES,
        _RABBIT_OPEN_EYES,
        _RABBIT_CLOSED_EYES,
        _RABBIT_OPEN_EYES,
    ],
    walk_frames=[
        # Rabbits "hop" — bigger vertical motion.
        _RABBIT_OPEN_EYES,
        _shift_down(_RABBIT_OPEN_EYES, 1),
        _shift_down(_RABBIT_OPEN_EYES, 2),
        _shift_down(_RABBIT_OPEN_EYES, 1),
        _RABBIT_OPEN_EYES,
        _RABBIT_OPEN_EYES,
    ],
    sleep_frames=[
        _shift_down(_RABBIT_CLOSED_EYES, 2),
        _shift_down(_RABBIT_CLOSED_EYES, 2),
        _shift_down(_RABBIT_CLOSED_EYES, 3),
        _shift_down(_RABBIT_CLOSED_EYES, 3),
    ],
    placeholder=_RABBIT_OPEN_EYES,
)


# ---- FRANK (black-and-tan dachshund) ----------------------------------------
# Classic black-and-tan markings: black body, tan eyebrows above the eye, tan
# muzzle, tan paws, tan chest. Long sausage-shaped body, short legs, tail up.
# Inspired by a real black-and-tan dachshund.
_DACHS_OPEN_EYES = [
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                  K             ",
    "                 KKK            ",
    "                KKKKKKK         ",
    "               KKKKKKKKK        ",
    "              KKKTTKKKKKK       ",
    "              KKKTKEKKKKK       ",
    "              KKKKKKTTKKL       ",
    "              KKKKKTTTTKL       ",
    "    KKKKKKKKKKKKKKKKKKKK        ",
    "   KKKKKKKKKKKKKKKKKKKKKK       ",
    "   KKKKKKKKKKKKKKKKKKKKKK       ",
    "   TKKKKKKKKKKKKKKKKKKKK        ",
    "   TTKKKKKKKKKKKKKKKKKK         ",
    "   TKKKKKKKKKKKKKKKKKKL         ",
    "    KK KK     KK KK             ",
    "    KK KK     KK KK             ",
    "    TT TT     TT TT             ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
    "                                ",
]
_DACHS_CLOSED_EYES = list(_DACHS_OPEN_EYES)
_DACHS_CLOSED_EYES[9]  = "              KKKTTKKKKKK       "
_DACHS_CLOSED_EYES[10] = "              KKKKEEKKKKK       "
_DACHS_CLOSED_EYES[11] = "              KKKKKKTTKKL       "

DACHSHUND = PetSpriteSet(
    name="dachshund",
    palette=_palette_dachshund(),
    idle_frames=[
        _DACHS_OPEN_EYES,
        _DACHS_OPEN_EYES,
        _shift_down(_DACHS_OPEN_EYES, 1),
        _shift_down(_DACHS_OPEN_EYES, 1),
        _DACHS_OPEN_EYES,
        _DACHS_OPEN_EYES,
        _DACHS_CLOSED_EYES,
        _DACHS_OPEN_EYES,
    ],
    walk_frames=[
        _DACHS_OPEN_EYES,
        _shift_horiz(_DACHS_OPEN_EYES, 1),
        _shift_down(_DACHS_OPEN_EYES, 1),
        _shift_horiz(_DACHS_OPEN_EYES, -1),
        _DACHS_OPEN_EYES,
        _shift_down(_shift_horiz(_DACHS_OPEN_EYES, 1), 1),
    ],
    sleep_frames=[
        _shift_down(_DACHS_CLOSED_EYES, 2),
        _shift_down(_DACHS_CLOSED_EYES, 2),
        _shift_down(_DACHS_CLOSED_EYES, 3),
        _shift_down(_DACHS_CLOSED_EYES, 3),
    ],
    placeholder=_DACHS_OPEN_EYES,
)


# =============================================================================
# Tray icon (uses the claw palette)
# =============================================================================
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


# =============================================================================
# Rendering
# =============================================================================
def render_frame(
    pixels: list[str], palette: dict[str, tuple[int, int, int, int]]
) -> Image.Image:
    h = len(pixels)
    w = max(len(row) for row in pixels)
    img = Image.new("RGBA", (w, h), TRANSPARENT)
    px = img.load()
    assert px is not None
    for y, row in enumerate(pixels):
        for x, ch in enumerate(row.ljust(w)):
            px[x, y] = palette.get(ch, TRANSPARENT)
    return img


def render_sheet(
    frames: list[list[str]], palette: dict[str, tuple[int, int, int, int]]
) -> Image.Image:
    rendered = [render_frame(f, palette) for f in frames]
    h = max(img.height for img in rendered)
    w = sum(img.width for img in rendered)
    sheet = Image.new("RGBA", (w, h), TRANSPARENT)
    x = 0
    for img in rendered:
        sheet.paste(img, (x, 0))
        x += img.width
    return sheet


def write_pet_sprites(pet: PetSpriteSet) -> None:
    sprites_dir = PETS_ROOT / pet.name / "sprites"
    sprites_dir.mkdir(parents=True, exist_ok=True)
    if pet.placeholder:
        ph = render_frame(pet.placeholder, pet.palette)
        ph_path = sprites_dir / "placeholder.png"
        ph.save(ph_path)
        print(f"wrote {ph_path}")
    for state, frames in [
        ("idle", pet.idle_frames),
        ("walk", pet.walk_frames),
        ("sleep", pet.sleep_frames),
    ]:
        sheet = render_sheet(frames, pet.palette)
        path = sprites_dir / f"{state}.png"
        sheet.save(path)
        print(f"wrote {path} ({sheet.size[0]}x{sheet.size[1]}, {len(frames)} frames)")


# =============================================================================
# Main
# =============================================================================
def main() -> None:
    for pet in (CLAW, RABBIT, DACHSHUND):
        write_pet_sprites(pet)

    # Tray icon (always uses the claw look — single per-app icon).
    TRAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tray = render_frame(_TRAY_PIXELS, _palette_claw())
    tray = tray.resize((tray.size[0] * 2, tray.size[1] * 2), Image.NEAREST)
    tray.save(TRAY_PATH)
    print(f"wrote {TRAY_PATH} ({tray.size[0]}x{tray.size[1]})")


if __name__ == "__main__":
    main()
