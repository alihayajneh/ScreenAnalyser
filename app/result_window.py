"""
app/result_window.py — Analysis result window (spinner → section cards).

Public API
──────────
  AnalysisWindow(root)
      .show_spinner(message)           Open window with animated spinner.
      .update_message(message)         Update spinner text mid-analysis.
      .show_results(title, md, img)    Transition spinner → section cards.
      .close()                         Destroy the window (used on error).

  show_error_popup(root, title, md_text)
      Standalone error popup (separate Toplevel, no screenshot).

Internal helpers (not exported):
  _parse_sections, _copy_flash, _centre_window, _build_section_card
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageTk

from .config import ICON_PATH
from .markdown_renderer import render_markdown

# Card accent colours (cycled across sections)
_ACCENTS = ["#1565c0", "#2e7d32", "#6a1b9a", "#bf360c", "#00695c"]
_THUMB_W = 310    # width of the screenshot panel in pixels


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _centre_window(win: tk.BaseWidget, w: int, h: int) -> None:
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def _apply_icon(win: tk.Toplevel) -> None:
    if ICON_PATH.exists():
        try:
            win.iconbitmap(str(ICON_PATH))
        except Exception:
            pass


def _parse_sections(md_text: str) -> list[tuple[str, str]]:
    """
    Split markdown into [(title, body), …] at # / ## headings.
    Content before the first heading is returned as ("Analysis", body).
    Returns a single ("Analysis", full_text) if no headings are found.
    """
    parts    = re.split(r"^(#{1,2} .+)$", md_text, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []

    if parts[0].strip():
        sections.append(("Analysis", parts[0].strip()))

    i = 1
    while i < len(parts) - 1:
        heading = re.sub(r"^#+\s*", "", parts[i]).strip()
        body    = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if heading or body:
            sections.append((heading, body))
        i += 2

    return sections or [("Analysis", md_text.strip())]


def _copy_flash(btn: ttk.Button, text: str, win: tk.BaseWidget) -> None:
    """Copy *text* to clipboard and briefly flash the button label."""
    win.clipboard_clear()
    win.clipboard_append(text)
    btn.config(text="Copied ✓")
    btn.after(1400, lambda: btn.config(text="Copy"))


def _build_section_card(
    parent:     tk.Widget,
    sec_title:  str,
    sec_body:   str,
    accent:     str,
    copy_win:   tk.BaseWidget,
) -> None:
    """Render a single coloured section card into *parent*."""
    stripe = tk.Frame(parent, bg=accent)
    stripe.pack(fill=tk.BOTH, pady=(0, 10))

    card = tk.Frame(stripe, bg="#ffffff", padx=12, pady=8)
    card.pack(fill=tk.BOTH, expand=True, padx=(4, 0))

    # Header row: title + Copy button
    hdr = tk.Frame(card, bg="#ffffff")
    hdr.pack(fill=tk.X, pady=(0, 6))

    tk.Label(hdr, text=sec_title,
             font=("Segoe UI", 12, "bold"),
             fg=accent, bg="#ffffff", anchor="w",
             ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    cb = ttk.Button(hdr, text="Copy", width=7)
    cb.config(command=lambda b=cb, t=sec_body: _copy_flash(b, t, copy_win))
    cb.pack(side=tk.RIGHT, padx=(8, 0))

    ttk.Separator(card, orient="horizontal").pack(fill=tk.X, pady=(0, 8))

    txt = tk.Text(card, wrap=tk.WORD, padx=4, pady=2,
                  relief=tk.FLAT, bd=0, bg="#ffffff", fg="#212121",
                  cursor="arrow", selectbackground="#b3d4f5",
                  font=("Segoe UI", 11))
    txt.pack(fill=tk.BOTH, expand=True)
    render_markdown(txt, sec_body)

    # Auto-size height to fit content
    txt.update_idletasks()
    lines = int(txt.index(tk.END).split(".")[0])
    txt.config(height=max(lines, 2), state=tk.DISABLED)


def _save_text(win: tk.BaseWidget, text: str, default_ext: str = ".md") -> None:
    """Open a Save-As dialog and write *text* to the chosen file."""
    path = filedialog.asksaveasfilename(
        parent      = win,
        defaultextension = default_ext,
        filetypes   = [("Markdown", "*.md"), ("Text file", "*.txt"), ("All files", "*.*")],
        title       = "Save results",
    )
    if path:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except Exception as exc:
            tk.messagebox.showerror("Save failed", str(exc), parent=win)


def _save_screenshot(win: tk.BaseWidget, screenshot: Image.Image) -> None:
    """Open a Save-As dialog and write *screenshot* to the chosen file."""
    path = filedialog.asksaveasfilename(
        parent      = win,
        defaultextension = ".png",
        filetypes   = [("PNG image", "*.png"), ("JPEG image", "*.jpg"), ("All files", "*.*")],
        title       = "Save screenshot",
    )
    if path:
        try:
            screenshot.save(path)
        except Exception as exc:
            tk.messagebox.showerror("Save failed", str(exc), parent=win)


def _build_results_layout(
    win:        tk.Toplevel,
    md_text:    str,
    screenshot: Optional[Image.Image],
) -> None:
    """
    Build the section-cards + screenshot layout inside *win*.
    Called both from AnalysisWindow.show_results and show_error_popup.
    """
    chrome = ttk.Frame(win, padding=(8, 8, 8, 6))
    chrome.pack(fill=tk.BOTH, expand=True)
    chrome.rowconfigure(0, weight=1)
    chrome.columnconfigure(0, weight=1)

    content = tk.Frame(chrome, bg="#f0f2f5")
    content.grid(row=0, column=0, columnspan=2, sticky="nsew")
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    if screenshot:
        content.columnconfigure(1, minsize=_THUMB_W + 16, weight=0)

    # ── Left: scrollable section cards ───────────────────────────────────────
    cards_canvas = tk.Canvas(content, bg="#f0f2f5", highlightthickness=0)
    cards_vbar   = ttk.Scrollbar(content, orient=tk.VERTICAL,
                                  command=cards_canvas.yview)
    cards_canvas.configure(yscrollcommand=cards_vbar.set)
    cards_vbar.grid(row=0, column=0, sticky="nse", padx=(0, 2))
    cards_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 18))

    cards_frame = ttk.Frame(cards_canvas, padding=(4, 4, 4, 4))
    cwin_id     = cards_canvas.create_window((0, 0), window=cards_frame, anchor="nw")

    cards_frame.bind("<Configure>",
                     lambda _e: cards_canvas.configure(
                         scrollregion=cards_canvas.bbox("all")))
    cards_canvas.bind("<Configure>",
                      lambda e: cards_canvas.itemconfig(cwin_id, width=e.width))
    win.bind("<MouseWheel>",
             lambda e: cards_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    for idx, (title, body) in enumerate(_parse_sections(md_text)):
        _build_section_card(cards_frame, title, body,
                            _ACCENTS[idx % len(_ACCENTS)], win)

    # ── Right: screenshot thumbnail ───────────────────────────────────────────
    if screenshot:
        right = tk.Frame(content, bg="#e4e7ec", width=_THUMB_W + 16)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right.pack_propagate(False)

        tk.Label(right, text="Captured Region",
                 font=("Segoe UI", 10, "bold"),
                 bg="#e4e7ec", fg="#455a64").pack(pady=(10, 4))
        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, padx=8, pady=(0, 6))

        orig_w, orig_h = screenshot.size
        thumb_h = max(1, int(orig_h * _THUMB_W / orig_w))
        thumb   = screenshot.resize((_THUMB_W, thumb_h), Image.LANCZOS)
        photo   = ImageTk.PhotoImage(thumb)

        MAX_H  = 460
        disp_h = min(thumb_h, MAX_H)
        ic = tk.Canvas(right, width=_THUMB_W, height=disp_h,
                       bg="#e4e7ec", highlightthickness=0)
        if thumb_h > MAX_H:
            isb = ttk.Scrollbar(right, orient=tk.VERTICAL, command=ic.yview)
            ic.configure(yscrollcommand=isb.set)
            isb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4))
        ic.pack(padx=8)
        ic.create_image(0, 0, anchor="nw", image=photo)
        ic.configure(scrollregion=(0, 0, _THUMB_W, thumb_h))
        ic._photo = photo   # prevent GC

        tk.Label(right, text=f"{orig_w} × {orig_h} px",
                 font=("Segoe UI", 9), bg="#e4e7ec", fg="#78909c",
                 ).pack(pady=(6, 10))

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = ttk.Frame(chrome)
    bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _copy_all() -> None:
        win.clipboard_clear()
        win.clipboard_append(md_text)

    ttk.Button(bottom, text="Copy All",        width=10, command=_copy_all).pack(side=tk.LEFT)
    ttk.Button(bottom, text="Save Results",    width=13,
               command=lambda: _save_text(win, md_text)).pack(side=tk.LEFT, padx=(4, 0))
    if screenshot:
        ttk.Button(bottom, text="Save Screenshot", width=15,
                   command=lambda: _save_screenshot(win, screenshot)).pack(side=tk.LEFT, padx=(4, 0))
    ttk.Button(bottom, text="Close", width=10, command=win.destroy).pack(side=tk.RIGHT)
    win.bind("<Escape>", lambda _: win.destroy())


# ─────────────────────────────────────────────────────────────────────────────
#  Raw-text layout  (OCR, translation)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_rtl(text: str) -> str:
    """
    Reshape Arabic/Hebrew glyphs and apply the Unicode BiDi algorithm so the
    text displays correctly inside a left-to-right tkinter Text widget.
    Falls back to the original string if the libraries are not installed.
    """
    try:
        import arabic_reshaper                      # type: ignore
        from bidi.algorithm import get_display      # type: ignore
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def _build_raw_layout(
    win:        tk.Toplevel,
    text:       str,
    screenshot: Optional[Image.Image],
    rtl:        bool = False,
) -> None:
    """
    Plain-text result layout: monospace scrollable text on the left,
    optional screenshot thumbnail on the right.
    Used for OCR and translation tasks.
    """
    if rtl:
        text = _apply_rtl(text)

    chrome = ttk.Frame(win, padding=(8, 8, 8, 6))
    chrome.pack(fill=tk.BOTH, expand=True)
    chrome.rowconfigure(0, weight=1)
    chrome.columnconfigure(0, weight=1)

    content = tk.Frame(chrome, bg="#1e1e2e")
    content.grid(row=0, column=0, columnspan=2, sticky="nsew")
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    if screenshot:
        content.columnconfigure(1, minsize=_THUMB_W + 16, weight=0)

    # ── Left: plain monospace text area ──────────────────────────────────────
    txt_frame = tk.Frame(content, bg="#1e1e2e")
    txt_frame.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
    txt_frame.rowconfigure(0, weight=1)
    txt_frame.columnconfigure(0, weight=1)

    txt = tk.Text(
        txt_frame,
        wrap=tk.WORD, padx=12, pady=10,
        relief=tk.FLAT, bd=0,
        bg="#1e1e2e", fg="#cdd6f4",
        insertbackground="#cdd6f4",
        selectbackground="#313244",
        font=("Segoe UI", 12) if rtl else ("Consolas", 11),
        cursor="arrow",
    )
    sb = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.grid(row=0, column=1, sticky="ns")
    txt.grid(row=0, column=0, sticky="nsew")

    txt.insert(tk.END, text)

    # Right-justify every line for RTL text.
    # Must be done via a tag (Text widget does not accept justify= in constructor).
    if rtl:
        try:
            txt.tag_configure("rtl", justify=tk.RIGHT)
            txt.tag_add("rtl", "1.0", tk.END)
        except tk.TclError:
            pass

    txt.config(state=tk.DISABLED)

    win.bind("<MouseWheel>",
             lambda e: txt.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ── Right: screenshot thumbnail ───────────────────────────────────────────
    if screenshot:
        right = tk.Frame(content, bg="#e4e7ec", width=_THUMB_W + 16)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 4), pady=4)
        right.pack_propagate(False)

        tk.Label(right, text="Captured Region",
                 font=("Segoe UI", 10, "bold"),
                 bg="#e4e7ec", fg="#455a64").pack(pady=(10, 4))
        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, padx=8, pady=(0, 6))

        orig_w, orig_h = screenshot.size
        thumb_h = max(1, int(orig_h * _THUMB_W / orig_w))
        thumb   = screenshot.resize((_THUMB_W, thumb_h), Image.LANCZOS)
        photo   = ImageTk.PhotoImage(thumb)

        MAX_H  = 380
        disp_h = min(thumb_h, MAX_H)
        ic = tk.Canvas(right, width=_THUMB_W, height=disp_h,
                       bg="#e4e7ec", highlightthickness=0)
        if thumb_h > MAX_H:
            isb = ttk.Scrollbar(right, orient=tk.VERTICAL, command=ic.yview)
            ic.configure(yscrollcommand=isb.set)
            isb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4))
        ic.pack(padx=8)
        ic.create_image(0, 0, anchor="nw", image=photo)
        ic.configure(scrollregion=(0, 0, _THUMB_W, thumb_h))
        ic._photo = photo

        tk.Label(right, text=f"{orig_w} × {orig_h} px",
                 font=("Segoe UI", 9), bg="#e4e7ec", fg="#78909c",
                 ).pack(pady=(6, 10))

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = ttk.Frame(chrome)
    bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    char_count = len(text)
    tk.Label(bottom, text=f"{char_count} characters",
             font=("Segoe UI", 9), fg="#888").pack(side=tk.LEFT, padx=(2, 8))

    def _copy() -> None:
        win.clipboard_clear()
        win.clipboard_append(text)
        copy_btn.config(text="Copied ✓")
        win.after(1400, lambda: copy_btn.config(text="Copy Text"))

    copy_btn = ttk.Button(bottom, text="Copy Text", width=12, command=_copy)
    copy_btn.pack(side=tk.LEFT)
    ttk.Button(bottom, text="Save Results",    width=13,
               command=lambda: _save_text(win, text, ".txt")).pack(side=tk.LEFT, padx=(4, 0))
    if screenshot:
        ttk.Button(bottom, text="Save Screenshot", width=15,
                   command=lambda: _save_screenshot(win, screenshot)).pack(side=tk.LEFT, padx=(4, 0))
    ttk.Button(bottom, text="Close", width=10, command=win.destroy).pack(side=tk.RIGHT)
    win.bind("<Escape>", lambda _: win.destroy())


# ─────────────────────────────────────────────────────────────────────────────
#  AnalysisWindow — spinner → results in-place transition
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisWindow:
    """
    A single Toplevel that starts as an animated spinner and transitions
    in-place to the full results layout when the analysis completes.

    Lifecycle
    ─────────
    1. show_spinner(message)     — opens the window
    2. update_message(message)   — update spinner text (optional)
    3. show_results(…)           — replaces spinner content with cards
       OR
       close()                   — destroys window (used on error path)
    """

    _DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, root: tk.Tk) -> None:
        self._root      = root
        self._win:      Optional[tk.Toplevel] = None
        self._spin_lbl: Optional[tk.Label]    = None
        self._spin_msg: Optional[tk.Label]    = None
        self._spin_idx  = 0
        self._after_id: Optional[str]         = None

    # ── Spinner phase ─────────────────────────────────────────────────────────

    def show_spinner(self, message: str) -> None:
        """Open the window (or update text) with the animated spinner."""
        if self._win is not None:
            try:
                if self._win.winfo_exists():
                    if self._spin_msg:
                        self._spin_msg.config(text=message)
                    return
            except tk.TclError:
                pass

        bg   = "#f8f9ff"
        win  = tk.Toplevel(self._root)
        self._win = win
        win.title("Screen Analyser — Analysing…")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", lambda: None)   # block close during analysis
        win.configure(bg=bg)
        _apply_icon(win)

        tk.Label(win, bg=bg).pack(pady=(18, 0))          # top spacer

        self._spin_lbl = tk.Label(win, text=self._DOTS[0],
                                  font=("Segoe UI", 28), fg="#1565c0", bg=bg)
        self._spin_lbl.pack()

        self._spin_msg = tk.Label(win, text=message,
                                  font=("Segoe UI", 11), fg="#37474f", bg=bg,
                                  wraplength=280, justify=tk.CENTER)
        self._spin_msg.pack(pady=(8, 24), padx=30)

        win.update_idletasks()
        _centre_window(win, 320, 160)
        self._tick()

    def update_message(self, message: str) -> None:
        """Update the spinner text while it is running."""
        if self._spin_msg:
            try:
                self._spin_msg.config(text=message)
            except tk.TclError:
                pass

    def _tick(self) -> None:
        if self._win is None:
            return
        try:
            if not self._win.winfo_exists():
                return
            self._spin_idx = (self._spin_idx + 1) % len(self._DOTS)
            if self._spin_lbl:
                self._spin_lbl.config(text=self._DOTS[self._spin_idx])
            self._after_id = self._win.after(80, self._tick)
        except tk.TclError:
            pass

    def _cancel_spinner(self) -> None:
        if self._after_id and self._win:
            try:
                self._win.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = None

    # ── Results phase ─────────────────────────────────────────────────────────

    def show_results(
        self,
        title:      str,
        md_text:    str,
        screenshot: Optional[Image.Image],
    ) -> None:
        """Tear down spinner and build section-cards layout in-place."""
        self._replace_content(
            title, lambda w: _build_results_layout(w, md_text, screenshot),
            width=(760 + _THUMB_W + 24) if screenshot else 760, height=580,
        )

    def show_raw_result(
        self,
        title:      str,
        text:       str,
        screenshot: Optional[Image.Image],
        rtl:        bool = False,
    ) -> None:
        """
        Tear down spinner and build a plain-text layout in-place.
        Used for OCR and translation output where raw text is more useful
        than parsed section cards.
        """
        self._replace_content(
            title, lambda w: _build_raw_layout(w, text, screenshot, rtl=rtl),
            width=(680 + _THUMB_W + 24) if screenshot else 680, height=480,
        )

    def _replace_content(self, title: str, builder, width: int, height: int) -> None:
        """Shared: cancel spinner, clear widgets, call builder, resize."""
        self._cancel_spinner()
        if self._win is None:
            return
        try:
            if not self._win.winfo_exists():
                return
        except tk.TclError:
            return

        for child in self._win.winfo_children():
            child.destroy()

        self._win.title(title)
        self._win.resizable(True, True)
        self._win.protocol("WM_DELETE_WINDOW", self._win.destroy)

        builder(self._win)

        self._win.update_idletasks()
        _centre_window(self._win, width, height)
        self._win.focus_force()
        self._win = None   # release — window lives independently

    # ── Teardown ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Destroy the spinner window (called before showing an error popup)."""
        self._cancel_spinner()
        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None


# ─────────────────────────────────────────────────────────────────────────────
#  Standalone error popup
# ─────────────────────────────────────────────────────────────────────────────

def show_error_popup(root: tk.Tk, title: str, md_text: str) -> None:
    """Show a standalone error window (no screenshot panel)."""
    win = tk.Toplevel(root)
    win.title(title)
    win.attributes("-topmost", True)
    win.resizable(True, True)
    _apply_icon(win)
    _build_results_layout(win, md_text, screenshot=None)
    win.update_idletasks()
    _centre_window(win, 680, 440)
    win.focus_force()
