"""Background agent: owns the QApplication, tray icon, and PetWindow lifecycle."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from tamagotchi.config import load_pet_config
from tamagotchi.controller import PetController
from tamagotchi.dialogues import DialogueBook
from tamagotchi.pet import Pet
from tamagotchi.platform_macos import hide_dock_icon
from tamagotchi.state import load_stats
from tamagotchi.window import PetWindow

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


class Agent:
    """Owns the Qt application, the system tray icon, and the pet window."""

    def __init__(self, pet_dir: Path) -> None:
        self.pet_dir = pet_dir
        self.config = load_pet_config(pet_dir)
        existing = QApplication.instance()
        self._app: QApplication = (
            existing if isinstance(existing, QApplication) else QApplication([])
        )
        self._app.setQuitOnLastWindowClosed(False)
        self._app.aboutToQuit.connect(self._on_about_to_quit)

        # Best-effort: hide the dock icon on macOS so we look like a true tray app.
        hide_dock_icon()

        self._window = PetWindow(pet_dir=pet_dir, config=self.config)
        self._pet = Pet.from_config(self.config)

        # Restore persisted stats if available.
        saved = load_stats(self.config.name)
        if saved is not None:
            self._pet.stats = saved

        self._dialogues = DialogueBook.load(pet_dir)
        self._controller = PetController(self._pet, self._window, self._dialogues)

        self._is_paused = False
        self._tray = self._build_tray()

    # ------------------------------------------------------------------
    # Tray menu
    # ------------------------------------------------------------------
    def _build_tray(self) -> QSystemTrayIcon:
        icon_path = ASSETS_DIR / "tray_icon.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        tray = QSystemTrayIcon(icon)
        tray.setToolTip(f"Tamagotchi — {self.config.name}")

        menu = QMenu()

        feed_action = QAction("Feed", menu)
        feed_action.triggered.connect(self._controller.feed)
        menu.addAction(feed_action)

        pet_action = QAction("Pet", menu)
        pet_action.triggered.connect(self._controller.pet_pet)
        menu.addAction(pet_action)

        menu.addSeparator()

        self._pause_action = QAction("Pause", menu)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.show()
        return tray

    def _toggle_pause(self) -> None:
        if self._is_paused:
            self._controller.resume()
            self._pause_action.setText("Pause")
        else:
            self._controller.pause()
            self._pause_action.setText("Resume")
        self._is_paused = not self._is_paused

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _quit(self) -> None:
        self._tray.hide()
        QApplication.quit()

    def _on_about_to_quit(self) -> None:
        # Final autosave on any clean shutdown path.
        self._controller.stop()
        self._controller.save()

    def run(self) -> int:
        self._window.spawn_at_random_bottom()
        self._window.show()
        self._controller.start()
        return int(QGuiApplication.exec())
