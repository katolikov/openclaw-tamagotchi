"""PetController: ticks a Pet on a QTimer and reflects its state in the PetWindow."""

from __future__ import annotations

import random

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication

from tamagotchi.animation import SpriteSheet, SpriteSheetError
from tamagotchi.config import resolve_sprite_path
from tamagotchi.dialogues import DialogueBook
from tamagotchi.pet import Pet, PetState
from tamagotchi.speech_bubble import SpeechBubble
from tamagotchi.state import save_stats
from tamagotchi.window import PetWindow

TICK_HZ = 10  # 10 ticks/sec — plenty for state transitions; cheap on CPU.

# How long a bubble hangs around. Phase 5 hard-codes this; could be configurable later.
BUBBLE_HOLD_MS = 3500
INITIAL_SPEECH_DELAY_RANGE_SEC = (3.0, 8.0)
SAVE_INTERVAL_MS = 60_000  # autosave every 60s

# When a mood applies, this is the chance the controller speaks the mood phrase
# instead of the state phrase. Keeps mood-talk noticeable but not relentless.
MOOD_PHRASE_PROBABILITY = 0.7


class PetController(QObject):
    """Owns the Pet, ticks it on a QTimer, swaps animations, and schedules speech."""

    def __init__(
        self,
        pet: Pet,
        window: PetWindow,
        dialogues: DialogueBook,
        *,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(window)
        self._pet = pet
        self._window = window
        self._dialogues = dialogues
        self._rng = rng if rng is not None else random.Random()

        # Pre-load all available animations from the config (right-facing).
        self._sheets: dict[PetState, SpriteSheet | None] = {}
        # Lazy cache of horizontally flipped sheets (built on first left-walk).
        self._flipped: dict[PetState, SpriteSheet | None] = {}
        for state in PetState:
            anim = pet.config.sprites.get(state.value)
            if anim is None:
                self._sheets[state] = None
                continue
            try:
                self._sheets[state] = SpriteSheet.load(
                    resolve_sprite_path(window.pet_dir, anim), frames=anim.frames
                )
            except SpriteSheetError:
                self._sheets[state] = None

        # Sync screen bounds, then apply the initial animation.
        self._sync_screen_bounds()
        self._apply_state_animation()
        self._last_state = pet.state
        self._last_facing = pet.facing

        # Speech: the bubble lives as long as the controller.
        self._bubble = SpeechBubble()

        # Wire up: clicking the pet makes it happier.
        window.clicked.connect(self._on_pet_clicked)

        # Tick timer (state machine + animation).
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.setInterval(int(round(1000 / TICK_HZ)))
        self._timer.timeout.connect(self._tick)

        # Speech scheduler: single-shot, reschedules itself.
        self._speech_timer = QTimer(self)
        self._speech_timer.setSingleShot(True)
        self._speech_timer.timeout.connect(self._utter)

        # Periodic autosave so progress survives crashes.
        self._save_timer = QTimer(self)
        self._save_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._save_timer.setInterval(SAVE_INTERVAL_MS)
        self._save_timer.timeout.connect(self.save)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._pet.x = float(self._window.x())
        self._timer.start()
        self._save_timer.start()
        # First utterance after a short random delay.
        lo, hi = INITIAL_SPEECH_DELAY_RANGE_SEC
        self._speech_timer.start(int(self._rng.uniform(lo, hi) * 1000))

    def stop(self) -> None:
        self._timer.stop()
        self._speech_timer.stop()
        self._save_timer.stop()
        self._bubble.hide()

    def pause(self) -> None:
        """Freeze the simulation but keep the window visible."""
        self._timer.stop()
        self._speech_timer.stop()
        self._bubble.hide()

    def resume(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
        if not self._speech_timer.isActive():
            self._schedule_next()

    def save(self) -> None:
        """Persist the pet's stats to disk (non-blocking; failures are silent)."""
        try:
            save_stats(self._pet.config.name, self._pet.stats)
        except OSError:
            pass

    def feed(self) -> None:
        self._pet.feed()
        self._bubble.set_anchor(self._pet_top_center_global())
        self._bubble.say("Yum!", hold_ms=1800)

    def pet_pet(self) -> None:
        """Respond to a 'pet' interaction (tray button or click)."""
        self._on_pet_clicked()

    @property
    def pet(self) -> Pet:
        return self._pet

    @property
    def bubble(self) -> SpeechBubble:
        return self._bubble

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        dt = 1.0 / TICK_HZ
        self._sync_screen_bounds()
        self._pet.tick(dt)

        state_changed = self._pet.state is not self._last_state
        facing_changed = (
            self._pet.state is PetState.WALK and self._pet.facing != self._last_facing
        )
        if state_changed or facing_changed:
            self._apply_state_animation()
            self._last_state = self._pet.state
            self._last_facing = self._pet.facing

        if self._pet.state is PetState.WALK:
            self._window.move(int(round(self._pet.x)), self._window.y())

        # Keep the bubble glued above the pet's head if visible.
        if self._bubble.isVisible():
            self._bubble.set_anchor(self._pet_top_center_global())

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------
    def _utter(self) -> None:
        text = self._pick_phrase()
        self._bubble.set_anchor(self._pet_top_center_global())
        self._bubble.say(text, hold_ms=BUBBLE_HOLD_MS)
        self._schedule_next()

    def _pick_phrase(self) -> str:
        """Return the next phrase, biased toward the current mood when one applies."""
        mood = self._pet.current_mood()
        if mood is not None and self._dialogues.has(mood):
            if self._rng.random() < MOOD_PHRASE_PROBABILITY:
                phrase = self._dialogues.pick_for_mood(mood)
                if phrase is not None:
                    return phrase
        return self._dialogues.pick_for_state(self._pet.state)

    def _on_pet_clicked(self) -> None:
        """A click (not a drag) on the pet boosts happiness and triggers a reaction."""
        self._pet.pet_action()
        # Brief positive bubble.
        self._bubble.set_anchor(self._pet_top_center_global())
        self._bubble.say("\u2665", hold_ms=1200)

    def _schedule_next(self) -> None:
        lo, hi = self._pet.config.behavior.speech_interval_sec
        delay_sec = self._rng.uniform(lo, hi)
        self._speech_timer.start(int(delay_sec * 1000))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pet_top_center_global(self) -> QPoint:
        local_top_center = QPoint(self._window.width() // 2, 0)
        return self._window.mapToGlobal(local_top_center)

    def _sync_screen_bounds(self) -> None:
        """Set the pet's screen bounds to whichever monitor it currently sits on."""
        center = QPoint(
            self._window.x() + self._window.width() // 2,
            self._window.y() + self._window.height() // 2,
        )
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self._pet.screen_left = float(geo.left())
        self._pet.screen_right = float(geo.right() - self._window.width())

    def _apply_state_animation(self) -> None:
        """Swap the window's animation to match state + facing direction."""
        state = self._pet.state
        sheet = self._sheets.get(state)
        anim_cfg = self._pet.config.sprites.get(state.value)

        if sheet is None or anim_cfg is None:
            state = PetState.IDLE
            sheet = self._sheets.get(state)
            anim_cfg = self._pet.config.sprites.get("idle")
        if sheet is None or anim_cfg is None:
            return

        # Mirror only when actively walking left.
        if self._pet.state is PetState.WALK and self._pet.facing == -1:
            sheet = self._get_flipped(state, sheet)

        self._window.set_animation(sheet, fps=anim_cfg.fps, loop=anim_cfg.loop)

    def _get_flipped(self, state: PetState, sheet: SpriteSheet) -> SpriteSheet:
        """Return (and cache) a horizontally mirrored variant of `sheet`."""
        cached = self._flipped.get(state)
        if cached is not None:
            return cached
        flipped = sheet.flipped_horizontally()
        self._flipped[state] = flipped
        return flipped
