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

# Ensure the project root is on sys.path so `import app` resolves correctly
# when the script is launched from a different working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import App

App().run()
