"""
app/rtl.py - Helpers for right-to-left text display.

This module keeps bidi/shaping settings in one place so raw text views and
markdown renderers can use the same display behavior.
"""

from __future__ import annotations

import re

from arabic_reshaper import ArabicReshaper, reshaper_config
from bidi.algorithm import get_display

_RTL_RE = re.compile(r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_LTR_RUN_RE = re.compile(r"([A-Za-z0-9_./:+\-]+)")

_RESHAPER_CONFIG = reshaper_config.default_config.copy()
_RESHAPER_CONFIG.update(
    {
        "delete_harakat": False,
        "shift_harakat_position": True,
        "delete_tatweel": False,
        "support_zwj": True,
        "support_ligatures": True,
    }
)
_RESHAPER = ArabicReshaper(configuration=_RESHAPER_CONFIG)


def is_rtl_text(text: str) -> bool:
    return bool(_RTL_RE.search(text))


def _display_line(line: str) -> str:
    if not line or not is_rtl_text(line):
        return line

    if _ARABIC_RE.search(line):
        line = _RESHAPER.reshape(line)

    # Protect embedded Latin tokens, identifiers, and paths so bidi reordering
    # does not split or reverse them inside RTL lines.
    line = _LTR_RUN_RE.sub(lambda m: f"\u200e{m.group(1)}\u200e", line)

    return get_display(line, base_dir="R")


def display_rtl_text(text: str) -> str:
    """
    Convert logical RTL text into the display form used by tkinter widgets.

    Line breaks are preserved. Lines without RTL characters are left untouched.
    """
    if not text or not is_rtl_text(text):
        return text

    return "".join(_display_line(line) for line in text.splitlines(keepends=True))
