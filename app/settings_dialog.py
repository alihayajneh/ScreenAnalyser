"""
app/settings_dialog.py - Settings modal dialog.

Public API
---------
  show_settings_dialog(root, cfg)

Reads and writes ``cfg`` (a Settings instance from app.config).
Must be called from the tkinter main thread.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .config import ICON_PATH, Settings
from .ollama_utils import list_models
from .tasks import LANGUAGES


def _centre_window(win: tk.BaseWidget, w: int, h: int) -> None:
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def show_settings_dialog(root: tk.Tk, cfg: Settings) -> None:
    """Open the settings modal. Blocks further tray interactions until closed."""
    dlg = tk.Toplevel(root)
    dlg.title("Screen Analyser — Settings")
    dlg.attributes("-topmost", True)
    dlg.resizable(False, False)
    dlg.grab_set()  # modal - blocks interaction with other windows

    if ICON_PATH.exists():
        try:
            dlg.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

    pad = {"padx": 14, "pady": 6}

    # API key / model selector
    ttk.Label(dlg, text="Ollama API Key", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, sticky="w", **pad
    )

    api_key_var = tk.StringVar(value=cfg.ollama_api_key)
    api_key_entry = ttk.Entry(dlg, textvariable=api_key_var, width=34, show="•")
    api_key_entry.grid(row=0, column=1, sticky="ew", **pad)

    ttk.Label(
        dlg,
        text="Required only for cloud models from ollama.com",
        foreground="#666",
        font=("Segoe UI", 9),
    ).grid(row=1, column=1, sticky="w", padx=14, pady=(0, 2))

    ttk.Label(dlg, text="Ollama Model", font=("Segoe UI", 10, "bold")).grid(
        row=2, column=0, sticky="w", **pad
    )

    model_var = tk.StringVar(value=cfg.model)
    model_cb = ttk.Combobox(
        dlg,
        textvariable=model_var,
        width=34,
        font=("Consolas", 10),
    )
    model_cb.grid(row=2, column=1, sticky="ew", **pad)

    status_lbl = ttk.Label(
        dlg,
        text="",
        foreground="#555",
        font=("Segoe UI", 9, "italic"),
    )
    status_lbl.grid(row=3, column=0, columnspan=2, sticky="w", padx=14)

    def _apply_models(names: list[str]) -> None:
        model_cb["values"] = names
        if not names:
            status_lbl.config(
                text="Could not reach Ollama or no local models are installed"
            )
            return

        if model_var.get() not in names:
            model_var.set(names[0])
            status_lbl.config(
                text=f"{len(names)} model(s) found - using {names[0]} in this session"
            )
        else:
            status_lbl.config(text=f"{len(names)} model(s) found")

    def _refresh() -> None:
        """Fetch available models from Ollama in a background thread."""
        dlg.after(0, lambda: status_lbl.config(text="Fetching models..."))

        def _worker() -> None:
            names = list_models(api_key_var.get())
            dlg.after(0, lambda: _apply_models(names))

        threading.Thread(target=_worker, daemon=True).start()

    ttk.Button(dlg, text="↺  Refresh list", command=_refresh).grid(
        row=4, column=1, sticky="e", padx=14, pady=(0, 4)
    )

    # Translation language pair
    ttk.Separator(dlg, orient="horizontal").grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=4
    )

    ttk.Label(dlg, text="Translation", font=("Segoe UI", 10, "bold")).grid(
        row=6, column=0, sticky="w", padx=14, pady=(4, 2)
    )

    ttk.Label(dlg, text="From").grid(row=7, column=0, sticky="w", padx=14, pady=4)
    from_var = tk.StringVar(value=cfg.translate_from)
    from_cb = ttk.Combobox(
        dlg,
        textvariable=from_var,
        width=26,
        values=["Auto-detect"] + LANGUAGES,
        state="readonly",
    )
    from_cb.grid(row=7, column=1, sticky="ew", padx=14, pady=4)

    ttk.Label(dlg, text="To").grid(row=8, column=0, sticky="w", padx=14, pady=4)
    to_var = tk.StringVar(value=cfg.translate_to)
    to_cb = ttk.Combobox(
        dlg,
        textvariable=to_var,
        width=26,
        values=LANGUAGES,
        state="readonly",
    )
    to_cb.grid(row=8, column=1, sticky="ew", padx=14, pady=4)

    # Thinking mode
    ttk.Separator(dlg, orient="horizontal").grid(
        row=9, column=0, columnspan=2, sticky="ew", padx=14, pady=4
    )

    thinking_var = tk.BooleanVar(value=cfg.thinking)
    ttk.Checkbutton(
        dlg,
        text="Enable thinking mode  (qwen3 / deepseek-r1 only)",
        variable=thinking_var,
    ).grid(row=10, column=0, columnspan=2, sticky="w", padx=14, pady=6)

    ttk.Label(
        dlg,
        text=(
            "When enabled, the model reasons step-by-step before answering.\n"
            "Slower but more thorough. The reasoning chain is shown in results."
        ),
        foreground="#666",
        font=("Segoe UI", 9),
        justify=tk.LEFT,
    ).grid(row=11, column=0, columnspan=2, sticky="w", padx=28, pady=(0, 8))

    # Save / Cancel
    ttk.Separator(dlg, orient="horizontal").grid(
        row=12, column=0, columnspan=2, sticky="ew", padx=14, pady=4
    )

    btn_row = ttk.Frame(dlg)
    btn_row.grid(row=13, column=0, columnspan=2, sticky="e", padx=14, pady=8)

    def _save() -> None:
        cfg.model = model_var.get()
        cfg.ollama_api_key = api_key_var.get()
        cfg.thinking = thinking_var.get()
        cfg.translate_from = from_var.get()
        cfg.translate_to = to_var.get()
        dlg.destroy()

    ttk.Button(btn_row, text="Save", width=10, command=_save).pack(
        side=tk.RIGHT, padx=(4, 0)
    )
    ttk.Button(btn_row, text="Cancel", width=10, command=dlg.destroy).pack(
        side=tk.RIGHT
    )

    dlg.bind("<Return>", lambda _: _save())
    dlg.bind("<Escape>", lambda _: dlg.destroy())

    dlg.update_idletasks()
    _centre_window(dlg, 460, dlg.winfo_reqheight() + 10)
    dlg.focus_force()

    # Kick off the model refresh after the dialog is visible.
    _refresh()
