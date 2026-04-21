"""
app/state.py — Shared inter-thread singletons.

Kept in a separate module so every other module can import just what it needs
without pulling in the entire app graph.

• ``ui_queue``        — worker threads → main tkinter thread message bus.
• ``processing_lock`` — set while a capture+analysis is in flight; prevents
                        double-triggers from the hotkey.

Queue message contract
──────────────────────
  ("status",        str)                  open spinner window / update text
  ("status_update", str)                  update spinner text (window already open)
  ("result",        (str, PIL.Image))     analysis done; show results
  ("error",         str)                  analysis failed; show error popup
  ("show_selector", None)                 hotkey fired; open region selector
  ("show_settings", None)                 tray menu item clicked
  ("quit",          None)                 tray quit clicked
"""

from __future__ import annotations

import queue
import threading

ui_queue: queue.Queue = queue.Queue()
processing_lock: threading.Event = threading.Event()
