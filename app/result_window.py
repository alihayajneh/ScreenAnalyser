"""
app/result_window.py - Browser-backed result window facade.

The rest of the app still calls AnalysisWindow as before, but the visible
surface is now the localhost browser UI from app.web_ui instead of Tk widgets.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from . import web_ui
from .toast import hide_progress_toast, show_progress_toast


class AnalysisWindow:
    """
    Compatibility wrapper used by app.main.

    Progress is shown as a small persistent popup. Browser windows are reserved
    for finished results and errors.
    """

    def __init__(self, root: object | None = None) -> None:
        self._root = root
        self._view_id: str | None = None

    def show_spinner(self, message: str) -> None:
        self._view_id = None
        self._show_status_toast(str(message))

    def update_message(self, message: str) -> None:
        self._show_status_toast(str(message))

    def _show_status_toast(self, message: str) -> None:
        if self._root is None:
            return
        try:
            show_progress_toast(self._root, message)  # type: ignore[arg-type]
        except Exception:
            pass

    def show_results(
        self,
        title: str,
        md_text: str,
        screenshot: Optional[Image.Image],
        rtl: bool = False,
    ) -> None:
        hide_progress_toast()
        self._view_id = web_ui.show_markdown_result(
            self._view_id,
            title,
            md_text,
            screenshot,
            rtl=rtl,
        )
        self._view_id = None

    def show_raw_result(
        self,
        title: str,
        text: str,
        screenshot: Optional[Image.Image],
        rtl: bool = False,
    ) -> None:
        hide_progress_toast()
        self._view_id = web_ui.show_raw_result(
            self._view_id,
            title,
            text,
            screenshot,
            rtl=rtl,
        )
        self._view_id = None

    def show_error(self, title: str, md_text: str) -> None:
        hide_progress_toast()
        self._view_id = web_ui.show_error_result(self._view_id, title, md_text)
        self._view_id = None

    def close(self) -> None:
        hide_progress_toast()
        self._view_id = None


def show_error_popup(root: object | None, title: str, md_text: str) -> None:
    hide_progress_toast()
    web_ui.show_error(title, md_text)
