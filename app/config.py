"""
app/config.py - App-wide constants, path helpers, and persistent Settings.

Nothing in this module imports from the rest of the package.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path


def resource_path(filename: str) -> Path:
    """Locate a bundled asset."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / filename
    return Path(__file__).parent.parent / filename


def writable_path(filename: str) -> Path:
    """Locate a writable file next to the exe or project root."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / filename
    return Path(__file__).parent.parent / filename


ICON_PATH = resource_path("icon.ico")
TRAY_TOOLTIP = "Screen Analyser"


_DEFAULTS: dict = {
    "model": "qwen3-vl:4b",
    "ollama_api_key": "",
    "thinking": False,
    "translate_from": "Auto-detect",
    "translate_to": "English",
}


class Settings:
    """Thread-safe, JSON-backed user settings."""

    def __init__(self) -> None:
        self._path = writable_path("settings.json")
        self._lock = threading.Lock()
        self._d: dict = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text("utf-8"))
                self._d.update({k: data[k] for k in data if k in _DEFAULTS})
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._d, indent=2), "utf-8")
        except Exception:
            pass

    @property
    def model(self) -> str:
        with self._lock:
            return str(self._d.get("model", _DEFAULTS["model"]))

    @model.setter
    def model(self, value: str) -> None:
        with self._lock:
            self._d["model"] = value.strip()
            self._save()

    @property
    def ollama_api_key(self) -> str:
        with self._lock:
            return str(self._d.get("ollama_api_key", _DEFAULTS["ollama_api_key"]))

    @ollama_api_key.setter
    def ollama_api_key(self, value: str) -> None:
        with self._lock:
            self._d["ollama_api_key"] = value.strip()
            self._save()

    @property
    def thinking(self) -> bool:
        with self._lock:
            return bool(self._d.get("thinking", _DEFAULTS["thinking"]))

    @thinking.setter
    def thinking(self, value: bool) -> None:
        with self._lock:
            self._d["thinking"] = bool(value)
            self._save()

    @property
    def translate_from(self) -> str:
        with self._lock:
            return str(self._d.get("translate_from", _DEFAULTS["translate_from"]))

    @translate_from.setter
    def translate_from(self, value: str) -> None:
        with self._lock:
            self._d["translate_from"] = value
            self._save()

    @property
    def translate_to(self) -> str:
        with self._lock:
            return str(self._d.get("translate_to", _DEFAULTS["translate_to"]))

    @translate_to.setter
    def translate_to(self, value: str) -> None:
        with self._lock:
            self._d["translate_to"] = value
            self._save()


cfg = Settings()
