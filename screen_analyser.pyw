"""
screen_analyser.pyw — Thin launcher.

The .pyw extension makes Windows use pythonw.exe (no console window).
All application logic lives in the app/ package.

Run without console:   double-click, or  pythonw screen_analyser.pyw
Run with console:      python screen_analyser.pyw
Build exe:             venv\\Scripts\\pyinstaller screen_analyser.spec
"""

import sys
import os
import ctypes

# ── Single-instance guard ─────────────────────────────────────────────────────
# Create a named Windows mutex.  If it already exists (ERROR_ALREADY_EXISTS =
# 183) another instance is running — exit silently.  The handle is kept alive
# in _mutex for the entire process lifetime so the mutex is not released early.

def _single_instance_guard():
    mutex = ctypes.windll.kernel32.CreateMutexW(
        None, False, "ScreenAnalyser_SingleInstance_Mutex"
    )
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
    return mutex   # keep reference alive — do NOT discard

_mutex = _single_instance_guard()

# ── Launch ────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import App

App().run()
