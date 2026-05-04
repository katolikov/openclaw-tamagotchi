"""Entry point for the tamagotchi CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tamagotchi.agent import Agent
from tamagotchi.config import ConfigError

DEFAULT_PETS_DIR = Path(__file__).resolve().parent.parent.parent / "pets"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tamagotchi",
        description="A desktop pet that lives on your screen.",
    )
    parser.add_argument(
        "--pet",
        default="claw",
        help="Name of the pet folder to load (default: claw).",
    )
    parser.add_argument(
        "--pets-dir",
        type=Path,
        default=DEFAULT_PETS_DIR,
        help=f"Directory containing pet folders (default: {DEFAULT_PETS_DIR}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    pet_dir = args.pets_dir / args.pet
    if not pet_dir.is_dir():
        print(f"error: pet directory not found: {pet_dir}", file=sys.stderr)
        return 2
    try:
        agent = Agent(pet_dir=pet_dir)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return agent.run()


if __name__ == "__main__":
    raise SystemExit(main())
