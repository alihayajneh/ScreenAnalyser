"""
app/tray.py — System-tray icon with organised submenus.

Public API
──────────
  SystemTray(on_task, on_quick, on_settings, on_about, on_quit).run()
      Blocking — call in a daemon thread.

Callbacks
─────────
  on_task(task_id)          user picked a task from Tasks ▶
  on_quick(mode)            user picked "fullscreen" or "clipboard"
  on_history(entry_id)      user picked a history entry
  on_history_clear()        user clicked Clear History
  on_settings()
  on_about()
  on_quit()
"""

from __future__ import annotations

from typing import Callable

import pystray
from PIL import Image, ImageDraw

from .config  import ICON_PATH, TRAY_TOOLTIP
from .history import history
from .tasks   import BUILTIN_TASKS, Task


def _build_icon_image() -> Image.Image:
    if ICON_PATH.exists():
        ico       = Image.open(ICON_PATH)
        ico.load()
        available = ico.ico.sizes()
        target    = (64, 64) if (64, 64) in available else max(available)
        return ico.ico.getimage(target).convert("RGBA").resize(
            (64, 64), Image.LANCZOS)

    img  = Image.new("RGBA", (64, 64), (30, 80, 160, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 22, 44, 42], fill=(255, 255, 255, 180))
    return img


class SystemTray:
    """
    Wraps pystray.  Presents an organised menu with submenus so features are
    easy to discover without being overwhelming.

    Menu layout
    ───────────
      Screen Analyser  (disabled title)
      ─────────────────
      Tasks ▶
        Describe Screen      CTRL+ALT+S
        Extract Text (OCR)   CTRL+ALT+T
        …
      Quick Capture ▶
        Full Screen (Describe)
        From Clipboard (OCR)
      History ▶
        HH:MM  Task name   (up to 5 most recent)
        ─────
        Clear History
      ─────────────────
      Settings…
      About & Shortcuts
      ─────────────────
      Quit
    """

    def __init__(
        self,
        on_task:          Callable[[str], None],
        on_quick:         Callable[[str], None],
        on_history:       Callable[[int], None],
        on_history_clear: Callable[[], None],
        on_settings:      Callable[[], None],
        on_about:         Callable[[], None],
        on_quit:          Callable[[], None],
    ) -> None:
        self._on_task          = on_task
        self._on_quick         = on_quick
        self._on_history       = on_history
        self._on_history_clear = on_history_clear
        self._on_settings      = on_settings
        self._on_about         = on_about
        self._on_quit          = on_quit
        self._icon: pystray.Icon | None = None

    # ── Menu builders ─────────────────────────────────────────────────────────

    def _task_cb(self, task: Task):
        def _cb(_icon, _item):
            self._on_task(task.id)
        return _cb

    def _quick_cb(self, mode: str):
        def _cb(_icon, _item):
            self._on_quick(mode)
        return _cb

    def _history_cb(self, entry_id: int):
        def _cb(_icon, _item):
            self._on_history(entry_id)
        return _cb

    def _build_tasks_submenu(self) -> pystray.Menu:
        items = []
        for task in BUILTIN_TASKS.values():
            label = task.name
            if task.hotkey:
                label += f"   {task.hotkey.upper()}"
            items.append(pystray.MenuItem(label, self._task_cb(task)))
        return pystray.Menu(*items)

    def _build_history_items(self):
        """
        Generator called by pystray each time the History submenu is opened.
        Must yield individual MenuItem / SEPARATOR objects — NOT a Menu wrapper.
        """
        entries = history.recent(5)
        if not entries:
            yield pystray.MenuItem("(no history yet)", None, enabled=False)
            return

        for entry in entries:
            label = f"{entry.timestamp}  {entry.task_name}"
            yield pystray.MenuItem(label, self._history_cb(entry.id))

        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Clear History",
                               lambda _i, _it: self._on_history_clear())

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the tray event loop (blocks until stop() is called)."""

        def _settings_cb(_icon, _item): self._on_settings()
        def _about_cb(_icon, _item):    self._on_about()
        def _quit_cb(icon, _item):      icon.stop(); self._on_quit()

        menu = pystray.Menu(
            pystray.MenuItem(TRAY_TOOLTIP, None, enabled=False),
            pystray.Menu.SEPARATOR,

            # ── Tasks submenu ─────────────────────────────────────────────
            pystray.MenuItem(
                "Tasks",
                self._build_tasks_submenu(),
            ),

            # ── Quick Capture submenu ─────────────────────────────────────
            pystray.MenuItem(
                "Quick Capture",
                pystray.Menu(
                    pystray.MenuItem(
                        "Full Screen (Describe)   CTRL+ALT+F",
                        self._quick_cb("fullscreen"),
                    ),
                    pystray.MenuItem(
                        "From Clipboard (OCR)",
                        self._quick_cb("clipboard"),
                    ),
                ),
            ),

            # ── History submenu (dynamic) ─────────────────────────────────
            pystray.MenuItem(
                "History",
                pystray.Menu(self._build_history_items),
            ),

            pystray.Menu.SEPARATOR,

            pystray.MenuItem("Settings\u2026",        _settings_cb),
            pystray.MenuItem("About & Shortcuts",  _about_cb),

            pystray.Menu.SEPARATOR,

            pystray.MenuItem("Quit", _quit_cb),
        )

        self._icon = pystray.Icon(
            name  = "ScreenAnalyser",
            icon  = _build_icon_image(),
            title = TRAY_TOOLTIP,
            menu  = menu,
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
