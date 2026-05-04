# HOWTO

Practical guide to running, customizing, and extending **openclaw-tamagotchi**.

- [Running it](#running-it)
- [Tray menu, keyboard, and mouse](#tray-menu-keyboard-and-mouse)
- [Where state is stored](#where-state-is-stored)
- [Adding your own pet](#adding-your-own-pet)
  - [pet.yaml schema](#petyaml-schema)
  - [dialogues.yaml schema](#dialoguesyaml-schema)
  - [Sprite sheet conventions](#sprite-sheet-conventions)
- [Importing OpenClaw assets](#importing-openclaw-assets)
- [Tuning behaviour](#tuning-behaviour)
- [macOS: hiding the dock icon and packaging](#macos-hiding-the-dock-icon-and-packaging)
- [Multi-monitor & multiple pets](#multi-monitor--multiple-pets)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Running it

```sh
tamagotchi                 # default pet ("claw")
tamagotchi --pet claw      # explicit
tamagotchi --pets-dir ./elsewhere --pet mypet
python -m tamagotchi --pet claw
```

The pet spawns at the bottom of the screen under your cursor. Launch the
command twice to get two pets — they're independent processes that don't
know about each other but won't fight over resources.

## Tray menu, keyboard, and mouse

| Action                    | Effect                                          |
| ------------------------- | ----------------------------------------------- |
| **Left-click** the pet    | Pets it. ♥ +5 happiness                         |
| **Left-click + drag**     | Move the pet anywhere on screen                 |
| Tray → **Feed**           | Restores hunger by ~30. Wakes the pet if asleep |
| Tray → **Pet**            | Same as left-clicking the pet                   |
| Tray → **Pause / Resume** | Freezes / unfreezes the simulation              |
| Tray → **Quit**           | Saves state, then exits                         |

Click vs. drag is decided by motion: a release within ≤4 px of the press
counts as a click; anything more is a drag.

## Where state is stored

Stats persist between launches as JSON, named after the pet. The location is
provided by [platformdirs](https://github.com/platformdirs/platformdirs):

| OS      | Path                                              |
| ------- | ------------------------------------------------- |
| macOS   | `~/Library/Application Support/tamagotchi/`       |
| Linux   | `~/.config/tamagotchi/` (or `$XDG_CONFIG_HOME`)   |
| Windows | `%APPDATA%\tamagotchi\`                           |

Saved every 60 s and on shutdown (`aboutToQuit`). Delete the JSON to reset.

The file shape:

```json
{
  "version": 1,
  "stats": { "hunger": 73.4, "energy": 48.0, "happiness": 92.1 }
}
```

## Adding your own pet

A pet is just a folder under `pets/` containing three things:

```
pets/<name>/
├── pet.yaml
├── dialogues.yaml
└── sprites/
    ├── idle.png         (required)
    ├── walk.png         (recommended)
    └── sleep.png        (recommended)
```

After creating the folder, run `tamagotchi --pet <name>`.

### pet.yaml schema

Validated by pydantic with `extra="forbid"` — typos in keys are rejected
loudly. All fields shown below; everything except `name`, `species`, and
`sprites.idle` has defaults.

```yaml
name: "Claw"                 # display name
species: "pirate_cat"
role: null                   # optional free-form tag for future skill-driven dialogue

sprites:
  idle:
    file: "sprites/idle.png" # path is relative to this pet folder
    frames: 8                # number of cells in the horizontal strip
    fps: 6                   # playback speed
    loop: true
  walk:  { file: "sprites/walk.png",  frames: 6, fps: 12, loop: true }
  sleep: { file: "sprites/sleep.png", frames: 4, fps: 3,  loop: true }

behavior:
  idle_to_walk_chance: 0.3       # probability per minute of starting to walk
  walk_speed_px_per_sec: 40
  sleep_after_idle_sec: 120      # nap if idle this long without walking
  speech_interval_sec: [12, 30]  # random delay between bubbles, in seconds

stats:
  hunger:    { initial: 100, decay_per_min: 0.5 }
  energy:    { initial: 100, decay_per_min: 0.3 }
  happiness: { initial: 100, decay_per_min: 0.4 }
```

`sprites.idle` is **mandatory**. Missing `walk`/`sleep` blocks transparently
fall back to the idle animation.

### dialogues.yaml schema

```yaml
# State-keyed phrases (idle is required)
idle:  ["Hmm...", "Just looking around.", "..."]
walk:  ["Off I go!", "Stretching my legs."]
sleep: ["Zzz...", "*soft snoring*"]

# Optional mood overrides — used when the corresponding stat is below threshold
hungry: ["I could use a snack.", "My belly is empty..."]
tired:  ["Need... to rest..."]
sad:    ["I'm a bit down today."]
```

Mood selection priority: **hunger ≤ 30 → "hungry"**, otherwise
**(awake) energy ≤ 35 → "tired"**, otherwise **happiness ≤ 30 → "sad"**.
When a mood applies the controller picks the mood phrase 70% of the time;
the rest of the time it still picks the state phrase, so mood-talk never
becomes monotonous.

### Sprite sheet conventions

- **Horizontal strip** — N frames laid out side-by-side
- **Equal cell widths** — sheet width must be a clean multiple of `frames`
- **PNG with alpha** — anything outside the character is transparent
- **Authored small, scaled at runtime** — author at e.g. 32×32 per frame and
  the renderer scales 2× nearest-neighbor for that pixel-art look. Override
  by passing `scale=` when constructing `PetWindow` (programmatic only).
- **Right-facing** — when walking left the controller mirrors the sheet for
  you. Don't author left-facing frames manually.

If you want an example: see `pets/claw/sprites/*.png` and the generator at
`scripts/generate_placeholders.py`.

## Importing OpenClaw assets

> ⚠️ This tool **does not** parse OpenClaw's binary `.REZ`, `.PID`, `.ANI`,
> `.PCX`, or `.WWD` files. You must extract those to PNG frames first using
> a community OpenClaw extractor.

Once you have a directory of PNG frames laid out like this:

```
extracted/
├── STAND/00000.png 00001.png ...
├── WALK/00000.png  00001.png ...
├── SLEEP/00000.png ...
└── (other folders are ignored)
```

…run the importer:

```sh
tamagotchi-import-openclaw \
    --source ./extracted \
    --pet-name claw_pirate \
    --output pets

tamagotchi --pet claw_pirate
```

What it does:

1. Discovers subdirectories matching the default mapping
   (`STAND`/`IDLE`/`WAIT` → `idle`, `WALK`/`RUN`/`MOVE` → `walk`,
   `SLEEP`/`REST`/`DEAD` → `sleep`). When two folders map to the same state,
   the one with more frames wins.
2. Sorts each folder's frames by their numeric prefix.
3. Composes one horizontal sprite sheet per state. Cell size is
   `(max_frame_w, max_frame_h)`; each frame is **bottom-aligned and
   horizontally centered** within its cell to match OpenClaw's anchoring.
4. Writes `pets/<pet-name>/sprites/{idle,walk,sleep}.png`.
5. Generates a stub `pet.yaml` (default FPS: idle 6, walk 12, sleep 3) and a
   stub `dialogues.yaml`. **You'll usually want to hand-edit these.**

Useful flags:

- `--dry-run` — print what would be written without touching disk
- `--overwrite` — replace an existing target folder

`idle` is required. The importer fails fast if no source folder maps to it.

## Tuning behaviour

Most knobs live in `pet.yaml`. A few internal thresholds are constants in
`src/tamagotchi/pet.py` — currently:

```python
LOW_ENERGY_THRESHOLD     = 25.0   # idle → sleep
RESTED_ENERGY_THRESHOLD  = 80.0   # sleep → idle
MIN_WALK_DURATION_SEC    = 4.0
MAX_WALK_DURATION_SEC    = 12.0
HUNGRY_THRESHOLD         = 30.0
SAD_THRESHOLD            = 30.0
TIRED_THRESHOLD          = 35.0
FEED_HUNGER_BOOST        = 30.0
PET_HAPPINESS_BOOST      = 5.0
```

Edit those if you want a sleepier or grumpier pet.

## macOS: hiding the dock icon and packaging

For dev work, install the optional `[macos]` extra:

```sh
pip install -e ".[macos]"
```

This pulls in `pyobjc-framework-Cocoa`. On startup the agent calls
`NSApplication.setActivationPolicy_(NSApplicationActivationPolicyAccessory)`,
which removes the dock icon mid-process. No Info.plist edits required.

For a fully native bundle (signed `.app`, no Python rocket icon ever
appearing, double-clickable from Finder), use
[py2app](https://py2app.readthedocs.io/):

```sh
pip install py2app
py2applet --make-setup src/tamagotchi/__main__.py
# Edit setup.py:
#   - Add 'LSUIElement': True to plist
#   - Add 'pets/' and 'assets/' to data_files
python setup.py py2app
```

## Multi-monitor & multiple pets

The pet uses `QGuiApplication.screenAt(<pet center>)` each tick, so dragging
it to a second monitor automatically updates its turn-around bounds. On
launch it spawns at the bottom of whichever screen the cursor is on.

Running two `tamagotchi` processes gives you two independent pets sharing
the same on-disk state file (one per pet *name*, not per process). If you
want two pets that both persist independently, give each its own pet folder
with a different `name:` field.

## Development

```sh
pip install -e ".[dev]"
pytest                # 89 tests, including offscreen-Qt smoke tests
mypy                  # --strict, clean
ruff check .          # clean
ruff format .         # auto-format
```

The test suite uses `QT_QPA_PLATFORM=offscreen` so it runs fine in CI without
a display. Logic-only modules (`pet.py`, `dialogues.py`, `state.py`,
`config.py`, `assets_pipeline/`) are Qt-free and tested in isolation.

## Troubleshooting

**The pet doesn't show up.**
Check the terminal for a `ConfigError` — usually a typo in `pet.yaml`. The
window is set to be transparent and on-top of everything; if it's still
invisible, drag suspect screen corners with your mouse to find it (try the
bottom edge first).

**The dock icon won't disappear on macOS.**
You probably skipped the `[macos]` extra:
```sh
pip install -e ".[macos]"
```
This is dev-only mitigation. For production, use py2app + `LSUIElement: True`.

**`mypy` complains about `PySide6` types.**
We don't ship any PySide6 stubs override; use the bundled types from PySide6
itself. If `pip` installed a partial wheel, try
`pip install --force-reinstall PySide6`.

**Speech bubbles never appear.**
They're scheduled `behavior.speech_interval_sec` seconds after launch (default
12–30 s for `claw`). Lower the lower bound in `pet.yaml` to test faster.

**The pet walks off-screen on Linux.**
Some Wayland compositors report incorrect available geometry. Try X11
(`QT_QPA_PLATFORM=xcb tamagotchi`).

**Stats keep resetting.**
Either (a) the persistence directory is read-only, or (b) you renamed the
pet between runs (state files are keyed by `pet.yaml:name`).
