"""
app/history.py — In-memory recent-analysis store.

Public API
──────────
  history  — module-level singleton (History instance)

  history.add(task, content, screenshot) -> HistoryEntry
  history.recent(n=5)                    -> list[HistoryEntry]   newest first
  history.get(entry_id)                  -> HistoryEntry | None
  history.clear()                        -> None
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PIL import Image


@dataclass
class HistoryEntry:
    id:          int
    timestamp:   str           # "HH:MM"
    task_name:   str
    raw_output:  bool          # True → show in raw layout; False → section cards
    content:     str
    screenshot:  Optional[Image.Image]


class History:
    """Thread-safe ring buffer of the last *max_size* analysis results."""

    def __init__(self, max_size: int = 20) -> None:
        self._lock:     threading.Lock         = threading.Lock()
        self._entries:  list[HistoryEntry]     = []
        self._counter:  int                    = 0
        self._max_size: int                    = max_size

    def add(
        self,
        task_name:  str,
        raw_output: bool,
        content:    str,
        screenshot: Optional[Image.Image],
    ) -> HistoryEntry:
        with self._lock:
            self._counter += 1
            entry = HistoryEntry(
                id         = self._counter,
                timestamp  = datetime.now().strftime("%H:%M"),
                task_name  = task_name,
                raw_output = raw_output,
                content    = content,
                screenshot = screenshot,
            )
            self._entries.append(entry)
            if len(self._entries) > self._max_size:
                self._entries.pop(0)
            return entry

    def recent(self, n: int = 5) -> list[HistoryEntry]:
        """Return the *n* most recent entries, newest first."""
        with self._lock:
            return list(reversed(self._entries[-n:]))

    def get(self, entry_id: int) -> Optional[HistoryEntry]:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    return e
            return None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


# Module-level singleton
history = History()
