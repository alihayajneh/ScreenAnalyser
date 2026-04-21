"""
app/toast.py — Lightweight auto-dismissing toast notification.

Public API
──────────
  show_toast(root, message, duration_ms=2500)

No extra dependencies — built entirely on tkinter.
The toast appears in the bottom-right corner and fades out automatically.
Must be called from the tkinter main thread.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def show_toast(root: tk.Tk, message: str, duration_ms: int = 2500) -> None:
    """
    Show a brief non-interactive notification in the bottom-right corner.
    Destroys itself after *duration_ms* milliseconds.
    """
    win = tk.Toplevel(root)
    win.overrideredirect(True)          # no title bar / borders
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.92)

    bg = "#1e1e2e"
    fg = "#cdd6f4"

    frame = tk.Frame(win, bg=bg, padx=16, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        frame, text=message,
        font=("Segoe UI", 10), fg=fg, bg=bg,
        justify=tk.LEFT, wraplength=280,
    ).pack()

    win.update_idletasks()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    # Position: bottom-right with a small margin
    win.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - 60}")

    # Click anywhere on the toast to dismiss early
    frame.bind("<Button-1>", lambda _: win.destroy())

    win.after(duration_ms, _fade_out, win, 15)


def _fade_out(win: tk.Toplevel, steps_left: int) -> None:
    """Reduce alpha over ~300 ms then destroy."""
    try:
        if not win.winfo_exists():
            return
        alpha = win.attributes("-alpha")
        if steps_left <= 0 or alpha <= 0.05:
            win.destroy()
            return
        win.attributes("-alpha", max(0.0, alpha - 0.07))
        win.after(20, _fade_out, win, steps_left - 1)
    except tk.TclError:
        pass
