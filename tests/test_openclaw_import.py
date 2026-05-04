"""Tests for the OpenClaw asset importer.

Each test builds a synthetic 'extracted' directory of PNGs to exercise the
discovery / composition / output stages without needing real OpenClaw assets.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from PIL import Image

from tamagotchi.assets_pipeline.openclaw_import import (
    DEFAULT_STATE_MAPPING,
    ImporterError,
    compose_sheet,
    discover_animations,
    main,
    write_pet_folder,
)
from tamagotchi.config import load_pet_config


# ---- helpers ---------------------------------------------------------------
def _make_png(path: Path, w: int, h: int, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (w, h), color).save(path)


def _build_extracted_tree(root: Path) -> Path:
    """Synthesize a STAND/WALK/SLEEP directory layout."""
    for i in range(4):
        _make_png(root / "STAND" / f"{i:05d}.png", 16, 20, (255, 0, 0, 255))
    for i in range(6):
        # Varying widths to test bottom-align + center compositing.
        _make_png(root / "WALK" / f"{i:05d}.png", 16 + (i % 2), 18, (0, 255, 0, 255))
    for i in range(3):
        _make_png(root / "SLEEP" / f"{i:05d}.png", 16, 12, (0, 0, 255, 255))
    # Unrelated subdirectory should be ignored.
    _make_png(root / "JUMP" / "00000.png", 16, 16, (255, 255, 0, 255))
    return root


# ---- discovery -------------------------------------------------------------
def test_discovery_finds_mapped_states(tmp_path: Path) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    found = discover_animations(src)
    assert set(found) == {"idle", "walk", "sleep"}
    assert len(found["idle"].frames) == 4
    assert len(found["walk"].frames) == 6
    assert len(found["sleep"].frames) == 3


def test_discovery_picks_directory_with_most_frames(tmp_path: Path) -> None:
    src = tmp_path / "src"
    # Both STAND and IDLE map to 'idle'; IDLE has more frames so it should win.
    for i in range(2):
        _make_png(src / "STAND" / f"{i:05d}.png", 16, 16, (1, 1, 1, 255))
    for i in range(5):
        _make_png(src / "IDLE" / f"{i:05d}.png", 16, 16, (2, 2, 2, 255))
    found = discover_animations(src)
    assert found["idle"].source_label == "IDLE"
    assert len(found["idle"].frames) == 5


def test_discovery_requires_idle(tmp_path: Path) -> None:
    src = tmp_path / "src"
    for i in range(2):
        _make_png(src / "WALK" / f"{i:05d}.png", 16, 16, (0, 0, 0, 255))
    with pytest.raises(ImporterError, match="idle"):
        discover_animations(src)


def test_discovery_missing_source_dir(tmp_path: Path) -> None:
    with pytest.raises(ImporterError, match="source directory"):
        discover_animations(tmp_path / "does_not_exist")


def test_discovery_skips_non_numeric_pngs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    for i in range(3):
        _make_png(src / "STAND" / f"{i:05d}.png", 16, 16, (0, 0, 0, 255))
    _make_png(src / "STAND" / "thumbnail.png", 4, 4, (0, 0, 0, 255))
    found = discover_animations(src)
    assert len(found["idle"].frames) == 3


# ---- compose ---------------------------------------------------------------
def test_compose_sheet_pads_to_max_cell(tmp_path: Path) -> None:
    paths = []
    for i, (w, h) in enumerate([(10, 14), (12, 14), (10, 16)]):
        p = tmp_path / f"{i}.png"
        _make_png(p, w, h, (123, 45, 67, 255))
        paths.append(p)
    sheet = compose_sheet(paths)
    # cell = (max_w, max_h) = (12, 16); 3 frames -> 36x16
    assert sheet.size == (36, 16)


def test_compose_sheet_empty_input_raises() -> None:
    with pytest.raises(ImporterError):
        compose_sheet([])


# ---- write_pet_folder ------------------------------------------------------
def test_write_pet_folder_produces_loadable_pet(tmp_path: Path) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    found = discover_animations(src)
    out = tmp_path / "pets"
    pet_dir = write_pet_folder("imported_test", out, found)
    assert pet_dir == out / "imported_test"
    assert (pet_dir / "sprites" / "idle.png").is_file()
    assert (pet_dir / "sprites" / "walk.png").is_file()
    assert (pet_dir / "sprites" / "sleep.png").is_file()
    assert (pet_dir / "pet.yaml").is_file()
    assert (pet_dir / "dialogues.yaml").is_file()

    # The generated pet.yaml must be valid against our own loader.
    cfg = load_pet_config(pet_dir)
    assert cfg.name == "Imported_Test"
    assert "idle" in cfg.sprites
    assert cfg.sprites["walk"].frames == 6


def test_write_pet_folder_refuses_overwrite_by_default(tmp_path: Path) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    found = discover_animations(src)
    out = tmp_path / "pets"
    write_pet_folder("p", out, found)
    with pytest.raises(ImporterError, match="already exists"):
        write_pet_folder("p", out, found)


def test_write_pet_folder_overwrites_when_asked(tmp_path: Path) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    found = discover_animations(src)
    out = tmp_path / "pets"
    write_pet_folder("p", out, found)
    write_pet_folder("p", out, found, overwrite=True)
    assert (out / "p" / "pet.yaml").is_file()


# ---- pet.yaml content ------------------------------------------------------
def test_generated_pet_yaml_has_expected_structure(tmp_path: Path) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    found = discover_animations(src)
    pet_dir = write_pet_folder("p", tmp_path / "out", found)
    yaml_text = (pet_dir / "pet.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(yaml_text)
    assert data["sprites"]["idle"]["frames"] == 4
    assert data["sprites"]["idle"]["loop"] is True
    assert data["sprites"]["walk"]["fps"] == 12
    assert data["stats"]["hunger"]["initial"] == 100


# ---- CLI -------------------------------------------------------------------
def test_cli_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    code = main(
        [
            "--source",
            str(src),
            "--pet-name",
            "any",
            "--output",
            str(tmp_path / "pets"),
            "--dry-run",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "idle" in captured.out
    # No files actually written.
    assert not (tmp_path / "pets").exists()


def test_cli_full_import(tmp_path: Path) -> None:
    src = _build_extracted_tree(tmp_path / "src")
    code = main(
        [
            "--source",
            str(src),
            "--pet-name",
            "imported",
            "--output",
            str(tmp_path / "pets"),
        ]
    )
    assert code == 0
    pet_dir = tmp_path / "pets" / "imported"
    assert (pet_dir / "pet.yaml").is_file()
    assert (pet_dir / "sprites" / "idle.png").is_file()


def test_cli_returns_2_on_missing_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "--source",
            str(tmp_path / "no_such"),
            "--pet-name",
            "x",
            "--output",
            str(tmp_path / "pets"),
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "source directory" in err


# ---- mapping ---------------------------------------------------------------
def test_default_mapping_contains_essential_keys() -> None:
    # Sanity check: ensure the default mapping is sufficient to satisfy 'idle' from
    # any of the typical OpenClaw stand/wait directories.
    keys = {k.upper() for k in DEFAULT_STATE_MAPPING}
    assert "STAND" in keys
    assert "WALK" in keys
    assert "SLEEP" in keys
