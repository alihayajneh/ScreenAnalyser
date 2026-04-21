"""
app/selector.py — Fullscreen region selector overlay.

Public API
──────────
  RegionSelector(root).run(callback)

The callback receives a (x1, y1, x2, y2) tuple in *actual screen pixels*
(DPI-scaled correctly), or None if the user pressed Esc or clicked without
dragging a meaningful area.

Must be called from the tkinter main thread.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Tuple

from PIL import Image, ImageGrab, ImageTk

BBox = Tuple[int, int, int, int]


class RegionSelector:
    """
    Shows a fullscreen darkened screenshot overlay.
    The user drags to select a rectangle; the selection is returned as a
    bounding box in actual screen pixels via *callback*.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root

    def run(self, callback: Callable[[Optional[BBox]], None]) -> None:
        """
        Open the overlay.  Calls ``callback(bbox)`` when done (main thread).
        ``bbox`` is None when cancelled or when the drag was too small.
        """
        # Take the screenshot *before* our overlay appears.
        bg_img  = ImageGrab.grab()
        actual_w, actual_h = bg_img.size

        win = tk.Toplevel(self._root)
        win.attributes("-fullscreen", True)
        win.attributes("-topmost", True)
        win.overrideredirect(True)

        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()

        # DPI scale factors: logical tkinter px → actual screen px
        scale_x = actual_w / sw
        scale_y = actual_h / sh

        # Darken the captured screen for the overlay background
        bg_resized = bg_img.resize((sw, sh), Image.LANCZOS).convert("RGBA")
        dim        = Image.new("RGBA", (sw, sh), (0, 0, 0, 140))
        composite  = Image.alpha_composite(bg_resized, dim).convert("RGB")
        photo      = ImageTk.PhotoImage(composite)

        canvas = tk.Canvas(win, width=sw, height=sh,
                           highlightthickness=0, cursor="crosshair")
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas._photo = photo   # prevent GC

        # Instruction text (hidden once dragging starts)
        instr_ids = [
            canvas.create_text(sw // 2, sh // 2 - 28,
                text="Drag to select a region",
                fill="white", font=("Segoe UI", 22, "bold"), anchor="center"),
            canvas.create_text(sw // 2, sh // 2 + 14,
                text="Press  Esc  to cancel",
                fill="#cccccc", font=("Segoe UI", 14), anchor="center"),
        ]

        start   = [0, 0]
        rect_id = [None]
        lbl_id  = [None]

        def _hide_instructions() -> None:
            for iid in instr_ids:
                canvas.itemconfigure(iid, state="hidden")

        def on_press(e: tk.Event) -> None:
            _hide_instructions()
            start[0], start[1] = e.x, e.y
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(
                e.x, e.y, e.x, e.y,
                outline="#00d4ff", width=2, dash=(6, 3),
            )

        def on_drag(e: tk.Event) -> None:
            if rect_id[0] is None:
                return
            canvas.coords(rect_id[0], start[0], start[1], e.x, e.y)
            w = abs(e.x - start[0])
            h = abs(e.y - start[1])
            lx = max(start[0], e.x) + 8
            ly = max(start[1], e.y) + 6
            label = f"{int(w * scale_x)} × {int(h * scale_y)} px"
            if lbl_id[0]:
                canvas.coords(lbl_id[0], lx, ly)
                canvas.itemconfigure(lbl_id[0], text=label)
            else:
                lbl_id[0] = canvas.create_text(
                    lx, ly, text=label,
                    fill="#00d4ff", font=("Segoe UI", 11, "bold"), anchor="nw")

        def on_release(e: tk.Event) -> None:
            x1 = min(start[0], e.x);  y1 = min(start[1], e.y)
            x2 = max(start[0], e.x);  y2 = max(start[1], e.y)
            win.destroy()
            if x2 - x1 > 8 and y2 - y1 > 8:
                callback((
                    int(x1 * scale_x), int(y1 * scale_y),
                    int(x2 * scale_x), int(y2 * scale_y),
                ))
            else:
                callback(None)

        def on_escape(_e: tk.Event) -> None:
            win.destroy()
            callback(None)

        canvas.bind("<ButtonPress-1>",   on_press)
        canvas.bind("<B1-Motion>",       on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        win.bind("<Escape>",             on_escape)
        win.focus_force()
