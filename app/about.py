"""
app/about.py — About & Keyboard Shortcuts dialog.

Public API
──────────
  show_about_dialog(root)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import ICON_PATH
from .tasks  import BUILTIN_TASKS


def show_about_dialog(root: tk.Tk) -> None:
    """Open a modal About & Shortcuts window."""
    win = tk.Toplevel(root)
    win.title("Screen Analyser — About & Shortcuts")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    if ICON_PATH.exists():
        try:
            win.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

    PAD = 20
    BG  = "#f8f9ff"
    win.configure(bg=BG)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg="#1565c0")
    hdr.pack(fill=tk.X)

    tk.Label(
        hdr,
        text="Screen Analyser",
        font=("Segoe UI", 16, "bold"),
        fg="#ffffff", bg="#1565c0",
    ).pack(pady=(16, 2), padx=PAD, anchor="w")

    tk.Label(
        hdr,
        text="Capture any screen region · analyse with a local AI vision model",
        font=("Segoe UI", 10),
        fg="#bbdefb", bg="#1565c0",
    ).pack(pady=(0, 14), padx=PAD, anchor="w")

    # ── Body ──────────────────────────────────────────────────────────────────
    body = tk.Frame(win, bg=BG, padx=PAD, pady=12)
    body.pack(fill=tk.BOTH, expand=True)

    # Keyboard shortcuts table
    tk.Label(body, text="Keyboard Shortcuts",
             font=("Segoe UI", 12, "bold"),
             fg="#1565c0", bg=BG).pack(anchor="w", pady=(0, 8))

    tbl = ttk.Frame(body)
    tbl.pack(fill=tk.X)

    style = ttk.Style()
    style.configure("About.TLabel", background=BG, font=("Segoe UI", 10))
    style.configure("AboutKey.TLabel", background="#e8eaf6",
                    font=("Consolas", 10), foreground="#283593",
                    padding=(6, 3))

    for row_idx, task in enumerate(BUILTIN_TASKS.values()):
        hotkey_text = task.hotkey.upper() if task.hotkey else "—"
        ttk.Label(tbl, text=task.name,
                  style="About.TLabel").grid(
            row=row_idx, column=0, sticky="w", padx=(0, 20), pady=2)
        ttk.Label(tbl, text=hotkey_text,
                  style="AboutKey.TLabel").grid(
            row=row_idx, column=1, sticky="w", pady=2)

    ttk.Separator(body, orient="horizontal").pack(fill=tk.X, pady=14)

    # Quick capture shortcuts
    tk.Label(body, text="Quick Capture",
             font=("Segoe UI", 12, "bold"),
             fg="#1565c0", bg=BG).pack(anchor="w", pady=(0, 8))

    quick = ttk.Frame(body)
    quick.pack(fill=tk.X)

    for row_idx, (label, key) in enumerate([
        ("Full Screen Capture", "CTRL+ALT+F"),
        ("Clipboard Image",     "—"),
    ]):
        ttk.Label(quick, text=label,
                  style="About.TLabel").grid(
            row=row_idx, column=0, sticky="w", padx=(0, 20), pady=2)
        ttk.Label(quick, text=key,
                  style="AboutKey.TLabel").grid(
            row=row_idx, column=1, sticky="w", pady=2)

    ttk.Separator(body, orient="horizontal").pack(fill=tk.X, pady=14)

    # Tips
    tk.Label(body, text="Tips",
             font=("Segoe UI", 12, "bold"),
             fg="#1565c0", bg=BG).pack(anchor="w", pady=(0, 6))

    tips = [
        "Drag to select any screen region, then release to analyse.",
        "OCR results are automatically copied to your clipboard.",
        "Switch models any time via Settings in the tray menu.",
        "Enable Thinking mode for deeper reasoning (slower).",
        "Recent results are saved in History for quick re-access.",
    ]
    for tip in tips:
        tk.Label(body, text=f"  \u2022  {tip}",
                 font=("Segoe UI", 10), fg="#37474f", bg=BG,
                 anchor="w", justify=tk.LEFT, wraplength=420,
                 ).pack(fill=tk.X, pady=1)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = tk.Frame(win, bg=BG, padx=PAD, pady=(0, PAD))
    footer.pack(fill=tk.X)

    ttk.Button(footer, text="Close", width=10,
               command=win.destroy).pack(side=tk.RIGHT)

    win.bind("<Escape>", lambda _: win.destroy())
    win.bind("<Return>", lambda _: win.destroy())

    # Centre on screen
    W, H = 480, 580
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    win.focus_force()
