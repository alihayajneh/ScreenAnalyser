"""
app/settings_dialog.py — Settings modal dialog.

Public API
──────────
  show_settings_dialog(root, cfg)

Reads and writes ``cfg`` (a Settings instance from app.config).
Must be called from the tkinter main thread.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

import ollama

from .config import ICON_PATH, Settings
from .tasks  import LANGUAGES


def _centre_window(win: tk.BaseWidget, w: int, h: int) -> None:
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def show_settings_dialog(root: tk.Tk, cfg: Settings) -> None:
    """Open the settings modal.  Blocks further tray interactions until closed."""
    dlg = tk.Toplevel(root)
    dlg.title("Screen Analyser — Settings")
    dlg.attributes("-topmost", True)
    dlg.resizable(False, False)
    dlg.grab_set()   # modal — blocks interaction with other windows

    if ICON_PATH.exists():
        try:
            dlg.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

    pad = {"padx": 14, "pady": 6}

    # ── Model selector ────────────────────────────────────────────────────────
    ttk.Label(dlg, text="Ollama Model", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, sticky="w", **pad)

    model_var = tk.StringVar(value=cfg.model)
    model_cb  = ttk.Combobox(dlg, textvariable=model_var, width=34,
                              font=("Consolas", 10))
    model_cb.grid(row=0, column=1, sticky="ew", **pad)

    status_lbl = ttk.Label(dlg, text="", foreground="#555",
                           font=("Segoe UI", 9, "italic"))
    status_lbl.grid(row=1, column=0, columnspan=2, sticky="w", padx=14)

    def _refresh() -> None:
        """Fetch available models from Ollama (runs in a background thread)."""
        status_lbl.config(text="Fetching models…")
        dlg.update_idletasks()
        try:
            result = ollama.list()
            names  = (
                [m.model for m in result.models]
                if hasattr(result, "models")
                else [m["name"] for m in result.get("models", [])]
            )
            model_cb["values"] = names
            status_lbl.config(text=f"{len(names)} model(s) found")
        except Exception as exc:
            status_lbl.config(text=f"Could not reach Ollama: {exc}")

    ttk.Button(dlg, text="↺  Refresh list", command=_refresh).grid(
        row=2, column=1, sticky="e", padx=14, pady=(0, 4))

    # ── Translation language pair ─────────────────────────────────────────────
    ttk.Separator(dlg, orient="horizontal").grid(
        row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=4)

    ttk.Label(dlg, text="Translation", font=("Segoe UI", 10, "bold")).grid(
        row=4, column=0, sticky="w", padx=14, pady=(4, 2))

    ttk.Label(dlg, text="From").grid(row=5, column=0, sticky="w", padx=14, pady=4)
    from_var = tk.StringVar(value=cfg.translate_from)
    from_cb  = ttk.Combobox(dlg, textvariable=from_var, width=26,
                             values=["Auto-detect"] + LANGUAGES, state="readonly")
    from_cb.grid(row=5, column=1, sticky="ew", padx=14, pady=4)

    ttk.Label(dlg, text="To").grid(row=6, column=0, sticky="w", padx=14, pady=4)
    to_var = tk.StringVar(value=cfg.translate_to)
    to_cb  = ttk.Combobox(dlg, textvariable=to_var, width=26,
                           values=LANGUAGES, state="readonly")
    to_cb.grid(row=6, column=1, sticky="ew", padx=14, pady=4)

    # ── Thinking mode ─────────────────────────────────────────────────────────
    ttk.Separator(dlg, orient="horizontal").grid(
        row=7, column=0, columnspan=2, sticky="ew", padx=14, pady=4)

    thinking_var = tk.BooleanVar(value=cfg.thinking)
    ttk.Checkbutton(
        dlg,
        text="Enable thinking mode  (qwen3 / deepseek-r1 only)",
        variable=thinking_var,
    ).grid(row=8, column=0, columnspan=2, sticky="w", padx=14, pady=6)

    ttk.Label(
        dlg,
        text=(
            "When enabled, the model reasons step-by-step before answering.\n"
            "Slower but more thorough. The reasoning chain is shown in results."
        ),
        foreground="#666", font=("Segoe UI", 9), justify=tk.LEFT,
    ).grid(row=9, column=0, columnspan=2, sticky="w", padx=28, pady=(0, 8))

    # ── Save / Cancel ─────────────────────────────────────────────────────────
    ttk.Separator(dlg, orient="horizontal").grid(
        row=10, column=0, columnspan=2, sticky="ew", padx=14, pady=4)

    btn_row = ttk.Frame(dlg)
    btn_row.grid(row=11, column=0, columnspan=2, sticky="e", padx=14, pady=8)

    def _save() -> None:
        cfg.model          = model_var.get()
        cfg.thinking       = thinking_var.get()
        cfg.translate_from = from_var.get()
        cfg.translate_to   = to_var.get()
        dlg.destroy()

    ttk.Button(btn_row, text="Save",   width=10, command=_save).pack(
        side=tk.RIGHT, padx=(4, 0))
    ttk.Button(btn_row, text="Cancel", width=10, command=dlg.destroy).pack(
        side=tk.RIGHT)

    dlg.bind("<Return>", lambda _: _save())
    dlg.bind("<Escape>", lambda _: dlg.destroy())

    dlg.update_idletasks()
    _centre_window(dlg, 420, dlg.winfo_reqheight() + 10)
    dlg.focus_force()

    # Kick off the model refresh in a background thread so the dialog opens instantly
    threading.Thread(target=_refresh, daemon=True).start()
