"""
app/markdown_renderer.py — Markdown → tkinter.Text renderer.

Public API
──────────
  render_markdown(widget, text)   Insert styled markdown into a tk.Text widget.

Supported syntax
────────────────
  # / ## / ###   Headings
  **bold**        Bold
  *italic*        Italic
  ***both***      Bold-italic
  `code`          Inline code
  ```fence```     Code block
  - / * / +       Bullet list
  1.              Numbered list
  > quote         Blockquote
  ---             Horizontal rule

No external dependencies beyond tkinter and re.
"""

from __future__ import annotations

import re
import tkinter as tk

from .rtl import display_rtl_text


# ─────────────────────────────────────────────────────────────────────────────
#  Tag definitions
# ─────────────────────────────────────────────────────────────────────────────

def _configure_tags(widget: tk.Text, rtl: bool = False) -> None:
    base_font = "Tahoma" if rtl else "Segoe UI"
    mono_font = "Consolas"
    widget.tag_configure("h1",
        font=(base_font, 20, "bold"), spacing1=16, spacing3=8,
        foreground="#1a237e")
    widget.tag_configure("h2",
        font=(base_font, 16, "bold"), spacing1=12, spacing3=6,
        foreground="#283593")
    widget.tag_configure("h3",
        font=(base_font, 13, "bold"), spacing1=8, spacing3=4,
        foreground="#1565c0")
    widget.tag_configure("bold",
        font=(base_font, 11, "bold"))
    widget.tag_configure("italic",
        font=(base_font, 11, "italic"))
    widget.tag_configure("bold_italic",
        font=(base_font, 11, "bold italic"))
    widget.tag_configure("code_inline",
        font=(mono_font, 10), background="#eff1f3", foreground="#c7254e")
    widget.tag_configure("code_block",
        font=(mono_font, 10), background="#f6f8fa", foreground="#24292e",
        lmargin1=14, lmargin2=14, spacing1=2, spacing3=2)
    widget.tag_configure("bullet",
        font=(base_font, 11), lmargin1=22, lmargin2=38, spacing1=2)
    widget.tag_configure("numbered",
        font=(base_font, 11), lmargin1=22, lmargin2=38, spacing1=2)
    widget.tag_configure("blockquote",
        font=(base_font, 11, "italic"), foreground="#555",
        lmargin1=22, lmargin2=22, background="#f9f9f9")
    widget.tag_configure("hr",
        font=(base_font, 7), foreground="#bbb", spacing1=6, spacing3=6)
    widget.tag_configure("normal",
        font=(base_font, 11), foreground="#212121")


# ─────────────────────────────────────────────────────────────────────────────
#  Inline parser
# ─────────────────────────────────────────────────────────────────────────────

_INLINE_RE = re.compile(
    r"(\*\*\*(.+?)\*\*\*"   # ***bold italic***
    r"|\*\*(.+?)\*\*"       # **bold**
    r"|\*(.+?)\*"           # *italic*
    r"|`(.+?)`)"            # `code`
)


def _insert_inline(widget: tk.Text, text: str, base: str = "normal", rtl: bool = False) -> None:
    """Insert a line of text, applying inline markdown formatting."""
    last = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > last:
            chunk = text[last:m.start()]
            widget.insert(tk.END, display_rtl_text(chunk) if rtl else chunk, base)
        if m.group(2):
            chunk = m.group(2)
            widget.insert(tk.END, display_rtl_text(chunk) if rtl else chunk, "bold_italic")
        elif m.group(3):
            chunk = m.group(3)
            widget.insert(tk.END, display_rtl_text(chunk) if rtl else chunk, "bold")
        elif m.group(4):
            chunk = m.group(4)
            widget.insert(tk.END, display_rtl_text(chunk) if rtl else chunk, "italic")
        elif m.group(5):
            widget.insert(tk.END, m.group(5), "code_inline")
        last = m.end()
    if last < len(text):
        chunk = text[last:]
        widget.insert(tk.END, display_rtl_text(chunk) if rtl else chunk, base)


# ─────────────────────────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_markdown(widget: tk.Text, text: str, rtl: bool = False) -> None:
    """
    Parse *text* as Markdown and insert styled content into *widget*.
    The widget is left in DISABLED (read-only) state when done.
    """
    _configure_tags(widget, rtl=rtl)
    widget.config(state=tk.NORMAL)
    widget.delete("1.0", tk.END)

    lines       = text.splitlines()
    i           = 0
    in_code_blk = False
    code_lines: list[str] = []

    while i < len(lines):
        line = lines[i]

        # ── Code fence ───────────────────────────────────────────────────────
        if line.strip().startswith("```"):
            if not in_code_blk:
                in_code_blk = True
                code_lines  = []
            else:
                in_code_blk = False
                block = "\n".join(code_lines) + "\n"
                widget.insert(tk.END, block, "code_block")
                widget.insert(tk.END, "\n")
                code_lines = []
            i += 1
            continue

        if in_code_blk:
            code_lines.append(line)
            i += 1
            continue

        # ── Horizontal rule ──────────────────────────────────────────────────
        if re.match(r"^[-*_]{3,}\s*$", line):
            widget.insert(tk.END, "─" * 60 + "\n", "hr")
            i += 1
            continue

        # ── Heading ──────────────────────────────────────────────────────────
        hdr = re.match(r"^(#{1,3})\s+(.*)", line)
        if hdr:
            chunk = hdr.group(2)
            widget.insert(tk.END, display_rtl_text(chunk) if rtl else chunk, f"h{len(hdr.group(1))}")
            widget.insert(tk.END, "\n")
            i += 1
            continue

        # ── Blockquote ───────────────────────────────────────────────────────
        if line.startswith("> "):
            _insert_inline(widget, line[2:] + "\n", "blockquote", rtl=rtl)
            i += 1
            continue

        # ── Bullet list ──────────────────────────────────────────────────────
        bul = re.match(r"^(\s*)[*\-+]\s+(.*)", line)
        if bul:
            widget.insert(tk.END, "•  ", "bullet")
            _insert_inline(widget, bul.group(2) + "\n", "bullet", rtl=rtl)
            i += 1
            continue

        # ── Numbered list ────────────────────────────────────────────────────
        num = re.match(r"^(\s*)(\d+\.)\s+(.*)", line)
        if num:
            widget.insert(tk.END, num.group(2) + "  ", "numbered")
            _insert_inline(widget, num.group(3) + "\n", "numbered", rtl=rtl)
            i += 1
            continue

        # ── Empty line ───────────────────────────────────────────────────────
        if line.strip() == "":
            widget.insert(tk.END, "\n")
            i += 1
            continue

        # ── Normal paragraph ─────────────────────────────────────────────────
        _insert_inline(widget, line + "\n", "normal", rtl=rtl)
        i += 1

    widget.config(state=tk.DISABLED)
