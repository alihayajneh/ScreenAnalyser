"""
app/main.py — Application entry point.

Wires all modules together and owns the tkinter main-thread queue-polling loop.

Adding a new feature
────────────────────
• New analysis mode   → add a Task to app/tasks.py  (no changes here)
• New UI action       → add a message type to state.py, handle it in _dispatch()
• New tray item       → extend SystemTray callbacks and _dispatch()
"""

from __future__ import annotations

import threading
import tkinter as tk
from typing import Optional, Tuple

import keyboard

from .about            import show_about_dialog
from .capture          import (
    run_analysis,
    run_analysis_clipboard,
    run_analysis_fullscreen,
)
from .config           import ICON_PATH, cfg
from .history          import history
from .result_window    import AnalysisWindow, show_error_popup
from .selector         import RegionSelector
from .settings_dialog  import show_settings_dialog
from .state            import processing_lock, ui_queue
from .tasks            import BUILTIN_TASKS, Task, get as get_task
from .toast            import show_toast
from .tray             import SystemTray

BBox = Tuple[int, int, int, int]

# Task used for full-screen quick-capture
_FULLSCREEN_TASK_ID = "describe"
# Task used for clipboard quick-capture
_CLIPBOARD_TASK_ID  = "ocr"
# Hotkey for full-screen capture
_FULLSCREEN_HOTKEY  = "ctrl+alt+f"


class App:
    """
    Top-level application controller.

    Call ``App().run()`` — it blocks until the user quits.
    """

    def __init__(self) -> None:
        self._root:         tk.Tk | None          = None
        self._analysis_win: AnalysisWindow | None = None
        self._selector:     RegionSelector | None = None
        self._tray:         SystemTray | None     = None

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        self._setup_root()
        self._start_tray()
        self._register_hotkeys()
        self._root.after(100, self._poll)
        self._root.mainloop()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _setup_root(self) -> None:
        root = tk.Tk()
        root.withdraw()
        root.title("Screen Analyser")
        if ICON_PATH.exists():
            try:
                root.iconbitmap(str(ICON_PATH))
            except Exception:
                pass
        self._root         = root
        self._analysis_win = AnalysisWindow(root)
        self._selector     = RegionSelector(root)

    def _start_tray(self) -> None:
        self._tray = SystemTray(
            on_task          = lambda task_id:  ui_queue.put(("show_selector",   task_id)),
            on_quick         = lambda mode:     ui_queue.put(("quick_capture",   mode)),
            on_history       = lambda entry_id: ui_queue.put(("show_history",    entry_id)),
            on_history_clear = lambda:          ui_queue.put(("history_clear",   None)),
            on_settings      = lambda:          ui_queue.put(("show_settings",   None)),
            on_about         = lambda:          ui_queue.put(("show_about",      None)),
            on_quit          = lambda:          ui_queue.put(("quit",            None)),
        )
        threading.Thread(target=self._tray.run, daemon=True, name="tray").start()

    def _register_hotkeys(self) -> None:
        """Register a global hotkey for every task that declares one, plus quick-capture."""
        for task in BUILTIN_TASKS.values():
            if task.hotkey:
                _id = task.id
                keyboard.add_hotkey(
                    task.hotkey,
                    lambda tid=_id: ui_queue.put(("show_selector", tid)),
                    suppress=False,
                )

        # Full-screen quick-capture hotkey
        keyboard.add_hotkey(
            _FULLSCREEN_HOTKEY,
            lambda: ui_queue.put(("quick_capture", "fullscreen")),
            suppress=False,
        )

    # ── Queue polling (100 ms tick on main thread) ────────────────────────────

    def _poll(self) -> None:
        import queue
        try:
            while True:
                msg_type, payload = ui_queue.get_nowait()
                try:
                    self._dispatch(msg_type, payload)
                except Exception:
                    pass   # one bad message must not kill the poll loop
        except queue.Empty:
            pass
        self._root.after(100, self._poll)

    def _dispatch(self, msg_type: str, payload: object) -> None:
        """Route a queue message to the correct handler."""

        if msg_type == "show_selector":
            self._on_show_selector(str(payload))

        elif msg_type == "quick_capture":
            self._on_quick_capture(str(payload))

        elif msg_type == "status":
            self._analysis_win.show_spinner(payload)            # type: ignore[arg-type]

        elif msg_type == "status_update":
            self._analysis_win.update_message(payload)          # type: ignore[arg-type]

        elif msg_type == "result":
            content, img, task = payload                        # type: ignore[misc]
            self._on_result(content, img, task)

        elif msg_type == "error":
            self._analysis_win.close()
            show_error_popup(self._root, "Screen Analyser — Error", payload)  # type: ignore[arg-type]

        elif msg_type == "show_history":
            self._on_show_history(int(payload))                 # type: ignore[arg-type]

        elif msg_type == "history_clear":
            history.clear()

        elif msg_type == "show_settings":
            show_settings_dialog(self._root, cfg)

        elif msg_type == "show_about":
            show_about_dialog(self._root)

        elif msg_type == "quit":
            keyboard.unhook_all_hotkeys()
            self._root.destroy()

    # ── Result handling ───────────────────────────────────────────────────────

    def _on_result(self, content: str, img, task: Task) -> None:
        """
        Route result to the correct display path based on task flags.

        task.raw_output  → plain monospace text window (OCR / translate)
        default          → markdown section-cards window
        task.auto_copy   → also silently copy to clipboard + toast
        """
        # Save to history
        history.add(
            task_name  = task.name,
            raw_output = task.raw_output,
            rtl        = task.rtl,
            content    = content,
            screenshot = img,
        )

        if task.auto_copy:
            self._root.clipboard_clear()
            self._root.clipboard_append(content)
            show_toast(
                self._root,
                f"✓  {task.name}\n{len(content)} characters copied to clipboard",
            )

        if task.raw_output:
            self._analysis_win.show_raw_result(task.name, content, img, rtl=task.rtl)
        else:
            self._analysis_win.show_results(task.name, content, img)

    # ── History ───────────────────────────────────────────────────────────────

    def _on_show_history(self, entry_id: int) -> None:
        entry = history.get(entry_id)
        if entry is None:
            return
        if processing_lock.is_set():
            return

        if entry.raw_output:
            self._analysis_win.show_raw_result(
                f"[History] {entry.task_name}  {entry.timestamp}",
                entry.content,
                entry.screenshot,
                rtl=entry.rtl,
            )
        else:
            self._analysis_win.show_results(
                f"[History] {entry.task_name}  {entry.timestamp}",
                entry.content,
                entry.screenshot,
            )

    # ── Quick capture ─────────────────────────────────────────────────────────

    def _on_quick_capture(self, mode: str) -> None:
        if processing_lock.is_set():
            return
        processing_lock.set()

        if mode == "fullscreen":
            task = get_task(_FULLSCREEN_TASK_ID)
            run_analysis_fullscreen(
                task     = task,
                model    = cfg.model,
                thinking = cfg.thinking,
                q        = ui_queue,
                lock     = processing_lock,
            )
        elif mode == "clipboard":
            task = get_task(_CLIPBOARD_TASK_ID)
            run_analysis_clipboard(
                task     = task,
                model    = cfg.model,
                thinking = cfg.thinking,
                q        = ui_queue,
                lock     = processing_lock,
            )

    # ── Region selector ───────────────────────────────────────────────────────

    def _on_show_selector(self, task_id: str) -> None:
        if processing_lock.is_set():
            return
        processing_lock.set()
        task = get_task(task_id)
        self._selector.run(lambda bbox: self._on_region_selected(bbox, task))

    def _on_region_selected(self, bbox: Optional[BBox], task: Task) -> None:
        if bbox is None:
            processing_lock.clear()
            return
        run_analysis(
            bbox     = bbox,
            task     = task,
            model    = cfg.model,
            thinking = cfg.thinking,
            q        = ui_queue,
            lock     = processing_lock,
        )
