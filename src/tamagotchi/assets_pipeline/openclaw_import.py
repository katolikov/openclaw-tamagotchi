"""Convert an extracted OpenClaw PNG asset directory into a tamagotchi pet folder.

What this script does *not* do:
    It does NOT parse OpenClaw's proprietary binary formats (.REZ archives,
    .PID images, .ANI animation tables, .PCX palettes, .WWD level data).
    Implementing those parsers from scratch is out of scope.

What this script *does* expect:
    A directory containing already-extracted PNG frames, grouped by
    animation in subdirectories. The default OpenClaw layout looks like:

        <source>/
            STAND/00000.png 00001.png ...
            WALK/00000.png  00001.png ...
            JUMP/00000.png  ...
            ...

    Use any standard OpenClaw extraction tool (e.g., wap32, claw-rez-extractor)
    to produce that layout from a CLAW.REZ file.

Output:
    <output>/<pet-name>/
        sprites/idle.png       # horizontal sprite sheet
        sprites/walk.png
        sprites/sleep.png
        pet.yaml
        dialogues.yaml          # copied from a template
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image

# Default mapping from OpenClaw subdirectory names to our internal state names.
# Source names are matched case-insensitively against the subdirectory's basename.
DEFAULT_STATE_MAPPING: dict[str, str] = {
    "STAND": "idle",
    "IDLE": "idle",
    "WAIT": "idle",
    "WALK": "walk",
    "RUN": "walk",
    "MOVE": "walk",
    "SLEEP": "sleep",
    "REST": "sleep",
    "DEAD": "sleep",  # last-resort fallback if the asset pack lacks a sleep
}

# Default playback speed per state (FPS). OpenClaw .ANI files encode this; we
# don't read them, so these are sensible defaults that match the existing claw pet.
DEFAULT_FPS: dict[str, int] = {
    "idle": 6,
    "walk": 12,
    "sleep": 3,
}

DIALOGUE_TEMPLATE = """\
idle:
  - "Hmm..."
  - "Just looking around."
  - "..."
walk:
  - "Off I go!"
  - "Stretching my legs."
sleep:
  - "Zzz..."
  - "*soft snoring*"
hungry:
  - "I could use a snack."
sad:
  - "Could use some company."
tired:
  - "I'm getting sleepy..."
"""

NUMERIC_PNG_RE = re.compile(r"^(\d+)\.png$", re.IGNORECASE)


class ImporterError(RuntimeError):
    """Raised when the importer can't satisfy the requested operation."""


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
@dataclass
class DiscoveredAnimation:
    """A group of frame files that will become one sprite sheet."""

    state: str  # our internal state name (idle/walk/sleep)
    source_label: str  # the subdirectory name in the source tree
    frames: list[Path] = field(default_factory=list)


def _list_numeric_pngs(directory: Path) -> list[Path]:
    """Return PNG files in `directory` sorted by their numeric prefix."""
    candidates: list[tuple[int, Path]] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        m = NUMERIC_PNG_RE.match(entry.name)
        if m is None:
            continue
        candidates.append((int(m.group(1)), entry))
    candidates.sort(key=lambda x: x[0])
    return [p for _, p in candidates]


def discover_animations(
    source_dir: Path,
    *,
    mapping: dict[str, str] = DEFAULT_STATE_MAPPING,
) -> dict[str, DiscoveredAnimation]:
    """Walk `source_dir` once and pick the best subdirectory for each target state.

    If multiple source folders map to the same state (e.g. STAND and IDLE both
    -> idle), the one with the most frames wins.
    """
    if not source_dir.is_dir():
        raise ImporterError(f"source directory not found: {source_dir}")

    upper_map = {k.upper(): v for k, v in mapping.items()}
    selected: dict[str, DiscoveredAnimation] = {}

    for entry in sorted(source_dir.iterdir()):
        if not entry.is_dir():
            continue
        target_state = upper_map.get(entry.name.upper())
        if target_state is None:
            continue
        frames = _list_numeric_pngs(entry)
        if not frames:
            continue
        candidate = DiscoveredAnimation(
            state=target_state, source_label=entry.name, frames=frames
        )
        existing = selected.get(target_state)
        if existing is None or len(candidate.frames) > len(existing.frames):
            selected[target_state] = candidate

    if "idle" not in selected:
        raise ImporterError(
            "no source folder mapped to 'idle'. "
            f"expected one of: {sorted(k for k, v in mapping.items() if v == 'idle')}"
        )
    return selected


# ---------------------------------------------------------------------------
# Sheet composition
# ---------------------------------------------------------------------------
def compose_sheet(frame_paths: Sequence[Path]) -> Image.Image:
    """Build a horizontal sprite sheet from individual frame PNGs.

    All frames are placed in cells of uniform size = max(frame.size). Within a
    cell, each frame is bottom-aligned and horizontally centered (matches how
    OpenClaw sprites are anchored).
    """
    if not frame_paths:
        raise ImporterError("compose_sheet: no frames supplied")

    images = [Image.open(p).convert("RGBA") for p in frame_paths]
    cell_w = max(img.width for img in images)
    cell_h = max(img.height for img in images)
    sheet_w = cell_w * len(images)
    sheet = Image.new("RGBA", (sheet_w, cell_h), (0, 0, 0, 0))

    for i, img in enumerate(images):
        x = i * cell_w + (cell_w - img.width) // 2
        y = cell_h - img.height  # bottom-align
        sheet.paste(img, (x, y), img)
    return sheet


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
@dataclass
class WrittenAnimation:
    state: str
    file: Path  # absolute path to the written sprite sheet
    frames: int
    cell_size: tuple[int, int]


def write_pet_folder(
    pet_name: str,
    output_dir: Path,
    animations: dict[str, DiscoveredAnimation],
    *,
    fps: dict[str, int] = DEFAULT_FPS,
    overwrite: bool = False,
) -> Path:
    """Materialize a pet folder at `output_dir/<pet_name>/`.

    Returns the path to the new pet folder.
    """
    pet_dir = output_dir / pet_name
    if pet_dir.exists():
        if not overwrite:
            raise ImporterError(
                f"target already exists: {pet_dir}. Pass --overwrite to replace it."
            )
        shutil.rmtree(pet_dir)
    sprites_dir = pet_dir / "sprites"
    sprites_dir.mkdir(parents=True)

    written: dict[str, WrittenAnimation] = {}
    for state, anim in animations.items():
        sheet = compose_sheet(anim.frames)
        out_path = sprites_dir / f"{state}.png"
        sheet.save(out_path)
        written[state] = WrittenAnimation(
            state=state,
            file=out_path,
            frames=len(anim.frames),
            cell_size=(sheet.width // len(anim.frames), sheet.height),
        )

    _write_pet_yaml(pet_dir, pet_name, written, fps=fps)
    (pet_dir / "dialogues.yaml").write_text(DIALOGUE_TEMPLATE, encoding="utf-8")
    return pet_dir


def _write_pet_yaml(
    pet_dir: Path,
    pet_name: str,
    written: dict[str, WrittenAnimation],
    *,
    fps: dict[str, int],
) -> None:
    sprites_block: dict[str, dict[str, object]] = {}
    for state, w in written.items():
        sprites_block[state] = {
            "file": f"sprites/{state}.png",
            "frames": w.frames,
            "fps": fps.get(state, 6),
            "loop": True,
        }

    payload: dict[str, object] = {
        "name": pet_name.title(),
        "species": "openclaw_imported",
        "sprites": sprites_block,
        "behavior": {
            "idle_to_walk_chance": 0.3,
            "walk_speed_px_per_sec": 40,
            "sleep_after_idle_sec": 120,
            "speech_interval_sec": [30, 90],
        },
        "stats": {
            "hunger": {"initial": 100, "decay_per_min": 0.5},
            "energy": {"initial": 100, "decay_per_min": 0.3},
            "happiness": {"initial": 100, "decay_per_min": 0.4},
        },
    }
    (pet_dir / "pet.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tamagotchi-import-openclaw",
        description=(
            "Convert an extracted OpenClaw PNG asset tree into a tamagotchi "
            "pet folder. NOTE: this tool does not read raw .REZ/.PID/.ANI "
            "files — extract those to PNG first using a community tool."
        ),
    )
    parser.add_argument("--source", type=Path, required=True, help="Extracted asset directory.")
    parser.add_argument(
        "--pet-name",
        required=True,
        help="Folder/identifier for the new pet (e.g. claw_pirate).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pets"),
        help="Parent directory in which the pet folder will be created (default: ./pets).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the target pet folder if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover animations and report what would be written without touching disk.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        animations = discover_animations(args.source)
    except ImporterError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print("Discovered animations:")
    for state, anim in animations.items():
        print(f"  {state:<6} <- {anim.source_label} ({len(anim.frames)} frames)")

    if args.dry_run:
        print("(dry-run; no files written)")
        return 0

    try:
        pet_dir = write_pet_folder(
            args.pet_name, args.output, animations, overwrite=args.overwrite
        )
    except ImporterError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"\nwrote pet folder: {pet_dir}")
    print(f"try it with: tamagotchi --pet {args.pet_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
