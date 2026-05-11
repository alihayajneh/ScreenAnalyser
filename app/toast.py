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


_current_toast: tk.Toplevel | None = None
_progress_toast: tk.Toplevel | None = None
_progress_label: tk.Label | None = None
_progress_bar: ttk.Progressbar | None = None


def show_toast(root: tk.Tk, message: str, duration_ms: int = 2500) -> None:
    """
    Show a brief non-interactive notification in the bottom-right corner.
    Destroys itself after *duration_ms* milliseconds.
    """
    global _current_toast
    hide_progress_toast()
    if _current_toast is not None:
        _destroy_toast(_current_toast)

    win = tk.Toplevel(root)
    _current_toast = win
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

    _position_toast(win, margin_bottom=60)

    # Click anywhere on the toast to dismiss early
    frame.bind("<Button-1>", lambda _: _destroy_toast(win))

    win.after(duration_ms, _fade_out, win, 15)


def show_progress_toast(root: tk.Tk, message: str) -> None:
    """
    Show or update a small persistent progress popup.

    It stays visible until ``hide_progress_toast()`` is called.
    """
    global _progress_toast, _progress_label, _progress_bar

    if _progress_toast is not None:
        try:
            if _progress_toast.winfo_exists():
                if _progress_label is not None:
                    _progress_label.config(text=message)
                _position_toast(_progress_toast, margin_bottom=76)
                _progress_toast.lift()
                return
        except tk.TclError:
            _progress_toast = None
            _progress_label = None
            _progress_bar = None

    win = tk.Toplevel(root)
    _progress_toast = win
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.96)

    bg = "#111827"
    fg = "#e5e7eb"
    muted = "#9ca3af"

    frame = tk.Frame(win, bg=bg, padx=16, pady=12)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        frame,
        text="Screen Analyser",
        font=("Segoe UI", 9, "bold"),
        fg=muted,
        bg=bg,
        anchor="w",
    ).pack(fill=tk.X)

    _progress_label = tk.Label(
        frame,
        text=message,
        font=("Segoe UI", 10),
        fg=fg,
        bg=bg,
        justify=tk.LEFT,
        wraplength=300,
        anchor="w",
    )
    _progress_label.pack(fill=tk.X, pady=(4, 8))

    _progress_bar = ttk.Progressbar(frame, mode="indeterminate", length=300)
    _progress_bar.pack(fill=tk.X)
    _progress_bar.start(12)

    _position_toast(win, margin_bottom=76)


def hide_progress_toast() -> None:
    """Close the persistent progress popup if it is visible."""
    global _progress_toast, _progress_label, _progress_bar
    if _progress_bar is not None:
        try:
            _progress_bar.stop()
        except tk.TclError:
            pass
    if _progress_toast is not None:
        try:
            if _progress_toast.winfo_exists():
                _progress_toast.destroy()
        except tk.TclError:
            pass
    _progress_toast = None
    _progress_label = None
    _progress_bar = None


def _position_toast(win: tk.Toplevel, margin_bottom: int = 60) -> None:
    win.update_idletasks()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - margin_bottom}")


def _destroy_toast(win: tk.Toplevel) -> None:
    """Destroy a toast and clear the singleton reference when appropriate."""
    global _current_toast
    try:
        if win.winfo_exists():
            win.destroy()
    except tk.TclError:
        pass
    if _current_toast is win:
        _current_toast = None


def _fade_out(win: tk.Toplevel, steps_left: int) -> None:
    """Reduce alpha over ~300 ms then destroy."""
    try:
        if not win.winfo_exists():
            return
        alpha = win.attributes("-alpha")
        if steps_left <= 0 or alpha <= 0.05:
            _destroy_toast(win)
            return
        win.attributes("-alpha", max(0.0, alpha - 0.07))
        win.after(20, _fade_out, win, steps_left - 1)
    except tk.TclError:
        pass
