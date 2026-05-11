"""
app/web_ui.py - Browser-based UI surfaces for Screen Analyser.

Tk remains the backend event loop and selection overlay. All rich user-facing
text, settings, and about pages are rendered by the system browser through a
small localhost server so RTL and mixed-direction text use the browser engine.
"""

from __future__ import annotations

import base64
import ctypes
import html
import json
import os
import secrets
import shutil
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from PIL import Image

from .config import ICON_PATH, cfg
from .ollama_utils import list_models
from .tasks import BUILTIN_TASKS, LANGUAGES


def _image_data_url(image: Optional[Image.Image]) -> str:
    if image is None:
        return ""

    buf = BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


_ICON_CACHE: dict[int, bytes] = {}


def _icon_png(size: int) -> bytes:
    cached = _ICON_CACHE.get(size)
    if cached is not None:
        return cached

    image = Image.open(ICON_PATH).convert("RGBA")
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    buf = BytesIO()
    image.save(buf, format="PNG")
    data = buf.getvalue()
    _ICON_CACHE[size] = data
    return data


def _app_browser_path() -> str | None:
    for name in ("msedge", "chrome", "brave", "vivaldi"):
        found = shutil.which(name)
        if found:
            return found

    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LocalAppData", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles", "")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Vivaldi/Application/vivaldi.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _app_window_args() -> list[str]:
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        screen_w = int(user32.GetSystemMetrics(0))
        screen_h = int(user32.GetSystemMetrics(1))
        width = max(900, int(screen_w * 0.70))
        height = max(650, int(screen_h * 0.70))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
    except Exception:
        width, height, x, y = 1280, 820, 0, 0
    return [f"--window-size={width},{height}", f"--window-position={x},{y}"]


def _open_url(url: str) -> bool:
    app_browser = _app_browser_path()
    if app_browser:
        try:
            subprocess.Popen(
                [
                    app_browser,
                    "--no-first-run",
                    *_app_window_args(),
                    f"--app={url}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except Exception:
            pass

    try:
        return webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        return False


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _BrowserUI:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._server_lock = threading.Lock()
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None
        self._port: int | None = None
        self._views: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        with self._server_lock:
            if self._server is not None:
                return
            server = _Server(("127.0.0.1", 0), _Handler)
            server.ui = self  # type: ignore[attr-defined]
            self._server = server
            self._port = int(server.server_address[1])
            self._thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
                name="browser-ui",
            )
            self._thread.start()

    def stop(self) -> None:
        with self._server_lock:
            server = self._server
            self._server = None
            self._port = None
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass

    def base_url(self) -> str:
        self.start()
        assert self._port is not None
        return f"http://127.0.0.1:{self._port}"

    def open_settings(self) -> None:
        _open_url(f"{self.base_url()}/settings")

    def open_about(self) -> None:
        _open_url(f"{self.base_url()}/about")

    def open_status(self, message: str) -> str:
        view_id = secrets.token_urlsafe(10)
        with self._lock:
            self._views[view_id] = {
                "kind": "status",
                "title": "Screen Analyser",
                "message": str(message),
                "text": "",
                "rtl": False,
                "screenshot_data_url": "",
            }
        _open_url(f"{self.base_url()}/view/{view_id}")
        return view_id

    def update_status(self, view_id: str | None, message: str) -> str:
        if not view_id:
            return self.open_status(message)

        with self._lock:
            state = self._views.get(view_id)
            if state is None:
                self._views[view_id] = {
                    "kind": "status",
                    "title": "Screen Analyser",
                    "message": str(message),
                    "text": "",
                    "rtl": False,
                    "screenshot_data_url": "",
                }
            else:
                state.update(kind="status", message=str(message))
        return view_id

    def set_raw_result(
        self,
        view_id: str | None,
        title: str,
        text: str,
        screenshot: Optional[Image.Image],
        rtl: bool = False,
    ) -> str:
        return self._set_result(view_id, "raw", title, text, screenshot, rtl)

    def set_markdown_result(
        self,
        view_id: str | None,
        title: str,
        text: str,
        screenshot: Optional[Image.Image],
        rtl: bool = False,
    ) -> str:
        return self._set_result(view_id, "markdown", title, text, screenshot, rtl)

    def open_error(self, title: str, text: str) -> str:
        view_id = secrets.token_urlsafe(10)
        self._set_result(view_id, "error", title, text, None, False)
        _open_url(f"{self.base_url()}/view/{view_id}")
        return view_id

    def close_view(self, view_id: str | None) -> None:
        if not view_id:
            return
        with self._lock:
            state = self._views.get(view_id)
            if state is not None and state.get("kind") == "status":
                state.update(
                    kind="error",
                    title="Screen Analyser",
                    text="The operation was cancelled.",
                    message="",
                )

    def get_view(self, view_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._views.get(view_id)
            return dict(state) if state is not None else None

    def _set_result(
        self,
        view_id: str | None,
        kind: str,
        title: str,
        text: str,
        screenshot: Optional[Image.Image],
        rtl: bool,
    ) -> str:
        if not view_id:
            view_id = secrets.token_urlsafe(10)
            should_open = True
        else:
            should_open = view_id not in self._views

        with self._lock:
            self._views[view_id] = {
                "kind": kind,
                "title": str(title),
                "message": "",
                "text": str(text),
                "rtl": bool(rtl),
                "screenshot_data_url": _image_data_url(screenshot),
            }

        if should_open:
            _open_url(f"{self.base_url()}/view/{view_id}")
        return view_id

    def settings_payload(self) -> dict[str, Any]:
        return {
            "model": cfg.model,
            "ollama_api_key": cfg.ollama_api_key,
            "thinking": cfg.thinking,
            "translate_from": cfg.translate_from,
            "translate_to": cfg.translate_to,
            "languages": LANGUAGES,
            "from_languages": ["Auto-detect", *LANGUAGES],
        }

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        if "model" in data:
            cfg.model = str(data.get("model", "")).strip()
        if "ollama_api_key" in data:
            cfg.ollama_api_key = str(data.get("ollama_api_key", "")).strip()
        if "thinking" in data:
            cfg.thinking = bool(data.get("thinking"))
        if "translate_from" in data:
            value = str(data.get("translate_from", "Auto-detect"))
            cfg.translate_from = value if value in ["Auto-detect", *LANGUAGES] else "Auto-detect"
        if "translate_to" in data:
            value = str(data.get("translate_to", "English"))
            cfg.translate_to = value if value in LANGUAGES else "English"
        return self.settings_payload()


_UI = _BrowserUI()


def start_browser_ui() -> None:
    _UI.start()


def stop_browser_ui() -> None:
    _UI.stop()


def open_status(message: str) -> str:
    return _UI.open_status(message)


def update_status(view_id: str | None, message: str) -> str:
    return _UI.update_status(view_id, message)


def show_raw_result(
    view_id: str | None,
    title: str,
    text: str,
    screenshot: Optional[Image.Image],
    rtl: bool = False,
) -> str:
    return _UI.set_raw_result(view_id, title, text, screenshot, rtl)


def show_markdown_result(
    view_id: str | None,
    title: str,
    text: str,
    screenshot: Optional[Image.Image],
    rtl: bool = False,
) -> str:
    return _UI.set_markdown_result(view_id, title, text, screenshot, rtl)


def show_error(title: str, text: str) -> str:
    return _UI.open_error(title, text)


def show_error_result(view_id: str | None, title: str, text: str) -> str:
    return _UI._set_result(view_id, "error", title, text, None, False)


def close_view(view_id: str | None) -> None:
    _UI.close_view(view_id)


def show_settings() -> None:
    _UI.open_settings()


def show_about() -> None:
    _UI.open_about()


class _Handler(BaseHTTPRequestHandler):
    server_version = "ScreenAnalyserUI/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    @property
    def ui(self) -> _BrowserUI:
        return self.server.ui  # type: ignore[attr-defined,return-value]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._redirect("/about")
            return
        if path == "/favicon.ico":
            self._send_file(ICON_PATH, "image/x-icon")
            return
        if path == "/icon-192.png":
            self._send_bytes(_icon_png(192), "image/png")
            return
        if path == "/icon-512.png":
            self._send_bytes(_icon_png(512), "image/png")
            return
        if path == "/manifest.webmanifest":
            self._send_manifest(_manifest_payload())
            return
        if path.startswith("/view/"):
            view_id = path.split("/", 2)[2]
            self._send_html(_view_page(view_id))
            return
        if path.startswith("/api/view/"):
            view_id = path.split("/", 3)[3]
            state = self.ui.get_view(view_id)
            if state is None:
                self._send_json({"error": "View not found"}, status=404)
            else:
                self._send_json(state)
            return
        if path == "/settings":
            self._send_html(_settings_page())
            return
        if path == "/about":
            self._send_html(_about_page())
            return
        if path == "/api/settings":
            self._send_json(self.ui.settings_payload())
            return
        if path == "/api/models":
            query = parse_qs(parsed.query)
            api_key = query.get("api_key", [cfg.ollama_api_key])[0]
            self._send_json({"models": list_models(api_key)})
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/settings":
            try:
                data = self._read_json()
                self._send_json({"ok": True, "settings": self.ui.save_settings(data)})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if path == "/api/models":
            try:
                data = self._read_json()
                api_key = str(data.get("api_key", cfg.ollama_api_key))
                self._send_json({"models": list_models(api_key)})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"models": [], "error": str(exc)}, status=400)
            return

        self._send_json({"error": "Not found"}, status=404)

    def _read_json(self) -> dict[str, Any]:
        raw_len = self.headers.get("Content-Length", "0")
        length = int(raw_len or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 1024 * 1024))
        text = raw.decode("utf-8")
        return json.loads(text) if text.strip() else {}

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_manifest(self, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except Exception:
            self._send_json({"error": "Not found"}, status=404)
            return
        self._send_bytes(body, content_type)

    def _send_html(self, document: str, status: int = 200) -> None:
        body = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def _view_page(view_id: str) -> str:
    return _VIEW_TEMPLATE.replace("__VIEW_ID__", json.dumps(view_id))


def _settings_page() -> str:
    return _SETTINGS_TEMPLATE


def _about_page() -> str:
    task_rows = []
    for task in BUILTIN_TASKS.values():
        hotkey = task.hotkey.upper() if task.hotkey else "-"
        task_rows.append(
            '<div class="shortcut-row">'
            f'<span>{html.escape(task.name)}</span>'
            f'<kbd>{html.escape(hotkey)}</kbd>'
            "</div>"
        )

    tips = [
        "Drag to select any screen region, then release to analyse.",
        "OCR results are copied to your clipboard automatically.",
        "Use Settings to choose local models or cloud models with an Ollama token.",
        "Recent results are available from the tray History menu.",
    ]
    tip_rows = "".join(f"<li>{html.escape(tip)}</li>" for tip in tips)
    return (
        _ABOUT_TEMPLATE
        .replace("__TASK_ROWS__", "\n".join(task_rows))
        .replace("__TIP_ROWS__", tip_rows)
    )


def _manifest_payload() -> dict[str, Any]:
    return {
        "name": "Screen Analyser",
        "short_name": "Screen Analyser",
        "description": "Capture a screen region and analyse it with Ollama vision models.",
        "start_url": "/about",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f5f7fb",
        "theme_color": "#0f766e",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }


_VIEW_TEMPLATE = """<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Screen Analyser</title>
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#0f766e">
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #64748b;
      --line: #d8e0ea;
      --accent: #0f766e;
      --danger: #b42318;
      --shadow: 0 10px 28px rgba(20, 30, 55, 0.10);
    }
    * { box-sizing: border-box; }
    html { overflow-y: scroll; }
    body {
      margin: 0;
      min-height: 100vh;
      overflow-x: hidden;
      overflow-y: scroll;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.55 "Segoe UI", Tahoma, Arial, sans-serif;
    }
    button, .button {
      appearance: none;
      border: 1px solid #c9d4e2;
      background: #fff;
      color: #152238;
      border-radius: 6px;
      padding: 8px 12px;
      font: 600 13px "Segoe UI", Tahoma, Arial, sans-serif;
      text-decoration: none;
      cursor: pointer;
    }
    button:hover, .button:hover { background: #f8fafc; }
    .page {
      width: min(calc(100vw - 36px), var(--app-width, 70vw));
      max-width: 100%;
      margin: 0 auto;
      padding: 18px;
    }
    .result-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 32%);
      gap: 18px;
      align-items: start;
    }
    .result-grid.no-shot { grid-template-columns: minmax(0, 1fr); }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
      overflow: hidden;
    }
    .toolbar {
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
      backdrop-filter: blur(8px);
    }
    h1 {
      margin: 0;
      font-size: 17px;
      line-height: 1.35;
      color: var(--accent);
    }
    .title {
      display: flex;
      align-items: center;
      gap: 9px;
      min-width: 0;
    }
    .app-icon {
      width: 24px;
      height: 24px;
      flex: 0 0 auto;
    }
    .title-text {
      overflow-wrap: anywhere;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .icon-btn {
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }
    .icon {
      width: 16px;
      height: 16px;
      flex: 0 0 auto;
      stroke: currentColor;
      fill: none;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .raw-text {
      padding: 22px 24px 30px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      unicode-bidi: plaintext;
      font-size: 18px;
      line-height: 1.9;
    }
    .rtl .raw-text,
    .rtl .section-body,
    .rtl .section-title {
      direction: rtl;
      text-align: right;
    }
    .ltr .raw-text,
    .ltr .section-body,
    .ltr .section-title {
      direction: ltr;
      text-align: left;
    }
    code, pre {
      direction: ltr;
      unicode-bidi: isolate;
      font-family: Consolas, "Cascadia Mono", monospace;
    }
    .sections {
      padding: 14px;
      display: grid;
      gap: 12px;
    }
    .section-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }
    .section-title {
      margin: 0;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #f8fafc;
      color: #123b63;
      font-size: 15px;
    }
    .section-body {
      padding: 12px 14px 14px;
      unicode-bidi: plaintext;
      white-space: normal;
    }
    .section-body p {
      margin: 0 0 10px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      unicode-bidi: plaintext;
    }
    .section-body p:last-child { margin-bottom: 0; }
    .section-body ul {
      margin: 0 0 10px;
      padding-inline-start: 24px;
    }
    .section-body li {
      margin: 4px 0;
      unicode-bidi: plaintext;
    }
    .section-body pre {
      margin: 8px 0 12px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f8fafc;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .shot {
      padding: 12px;
    }
    .shot-title {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .shot img {
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #eef2f7;
    }
    .center {
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .status {
      width: min(420px, 100%);
      padding: 28px;
      text-align: center;
    }
    .spinner {
      width: 42px;
      height: 42px;
      margin: 0 auto 16px;
      border: 4px solid #d8e0ea;
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.85s linear infinite;
    }
    .status-text {
      margin: 8px 0 0;
      color: var(--muted);
    }
    .error-title { color: var(--danger); }
    .error-box {
      padding: 18px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      unicode-bidi: plaintext;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <main id="app"></main>
  <script>
    const VIEW_ID = __VIEW_ID__;
    let currentFingerprint = "";
    const ICONS = {
      copy: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
      save: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"></path><path d="m7 10 5 5 5-5"></path><path d="M5 21h14"></path></svg>',
      image: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="9" cy="9" r="2"></circle><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"></path></svg>'
    };

    function icon(name) {
      return ICONS[name] || "";
    }

    function setAppWidth() {
      const width = Math.max(900, Math.round(window.screen.availWidth * 0.70));
      document.documentElement.style.setProperty("--app-width", `${width}px`);
    }

    window.addEventListener("resize", setAppWidth);
    setAppWidth();

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[ch]);
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, "&#96;");
    }

    async function copyText(text) {
      try {
        await navigator.clipboard.writeText(text || "");
      } catch (err) {
        const area = document.createElement("textarea");
        area.value = text || "";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
    }

    function downloadBlob(name, blob) {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = name || "screen-analyser-result.txt";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    async function saveBlob(name, blob, types) {
      if (window.showSaveFilePicker) {
        try {
          const handle = await window.showSaveFilePicker({
            suggestedName: name,
            types: types
          });
          const writable = await handle.createWritable();
          await writable.write(blob);
          await writable.close();
          return;
        } catch (err) {
          if (err && err.name === "AbortError") {
            return;
          }
        }
      }
      downloadBlob(name, blob);
    }

    async function saveTextFile(name, text, ext) {
      const mime = ext === "md" ? "text/markdown" : "text/plain";
      const filename = `${name || "screen-analyser-result"}.${ext}`;
      const blob = new Blob([text || ""], { type: `${mime};charset=utf-8` });
      await saveBlob(filename, blob, [{
        description: ext === "md" ? "Markdown document" : "Text document",
        accept: { [mime]: [`.${ext}`] }
      }]);
    }

    async function saveImageFile(name, dataUrl) {
      if (!dataUrl) {
        return;
      }
      const response = await fetch(dataUrl);
      const blob = await response.blob();
      await saveBlob(`${name || "screen-analyser-result"}-capture.png`, blob, [{
        description: "PNG image",
        accept: { "image/png": [".png"] }
      }]);
    }

    function slugName(title) {
      return String(title || "screen-analyser-result")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 48) || "screen-analyser-result";
    }

    function parseSections(text) {
      const lines = String(text || "").replace(/\\r\\n/g, "\\n").split("\\n");
      const sections = [];
      let current = { title: "Result", body: [] };
      let sawHeading = false;

      for (const line of lines) {
        const match = line.match(/^#{1,3}\\s+(.+)$/);
        if (match) {
          if (sawHeading || current.body.join("\\n").trim()) {
            sections.push(current);
          }
          current = { title: match[1].trim(), body: [] };
          sawHeading = true;
        } else {
          current.body.push(line);
        }
      }

      if (sawHeading || current.body.join("\\n").trim() || sections.length === 0) {
        sections.push(current);
      }
      return sections;
    }

    function renderInline(text) {
      let value = escapeHtml(text);
      value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
      value = value.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
      return value;
    }

    function renderBody(lines) {
      let out = [];
      let inList = false;
      let inCode = false;
      let codeLines = [];

      function closeList() {
        if (inList) {
          out.push("</ul>");
          inList = false;
        }
      }
      function closeCode() {
        if (inCode) {
          out.push(`<pre><code>${escapeHtml(codeLines.join("\\n"))}</code></pre>`);
          inCode = false;
          codeLines = [];
        }
      }

      for (const rawLine of lines) {
        const line = String(rawLine);
        if (line.trim().startsWith("```")) {
          if (inCode) {
            closeCode();
          } else {
            closeList();
            inCode = true;
          }
          continue;
        }
        if (inCode) {
          codeLines.push(line);
          continue;
        }

        const bullet = line.match(/^\\s*[-*]\\s+(.+)$/);
        if (bullet) {
          if (!inList) {
            out.push("<ul>");
            inList = true;
          }
          out.push(`<li>${renderInline(bullet[1])}</li>`);
          continue;
        }

        closeList();
        if (line.trim() === "") {
          out.push("<p></p>");
        } else {
          out.push(`<p>${renderInline(line)}</p>`);
        }
      }
      closeCode();
      closeList();
      return out.join("");
    }

    function resultChrome(state, bodyHtml, ext) {
      const dirClass = state.rtl ? "rtl" : "ltr";
      const dir = state.rtl ? "rtl" : "ltr";
      const title = escapeHtml(state.title || "Screen Analyser");
      const filename = slugName(state.title);
      const shot = state.screenshot_data_url
        ? `<aside class="panel shot"><p class="shot-title">Captured image</p><img src="${escapeAttr(state.screenshot_data_url)}" alt="Captured screenshot"></aside>`
        : "";
      const shotAction = state.screenshot_data_url
        ? `<button class="icon-btn" type="button" title="Save image" onclick="saveImageFile('${filename}', window.RESULT_IMAGE)">${icon("image")}<span>Save image</span></button>`
        : "";

      return `<div class="page ${dirClass}">
        <div class="result-grid ${shot ? "" : "no-shot"}">
          <section class="panel">
            <div class="toolbar">
              <h1 class="title"><img class="app-icon" src="/icon-192.png" alt=""><span class="title-text">${title}</span></h1>
              <div class="actions">
                <button class="icon-btn" type="button" title="Copy text" onclick="copyText(window.RESULT_TEXT)">${icon("copy")}<span>Copy text</span></button>
                <button class="icon-btn" type="button" title="Save text" onclick="saveTextFile('${filename}', window.RESULT_TEXT, '${ext}')">${icon("save")}<span>Save text</span></button>
                ${shotAction}
              </div>
            </div>
            <div dir="${dir}">${bodyHtml}</div>
          </section>
          ${shot}
        </div>
      </div>`;
    }

    function render(state) {
      document.title = state.title || "Screen Analyser";
      document.documentElement.dir = state.rtl ? "rtl" : "ltr";
      document.documentElement.lang = state.rtl ? "ar" : "en";
      window.RESULT_TEXT = state.text || "";
      window.RESULT_IMAGE = state.screenshot_data_url || "";

      const app = document.getElementById("app");
      if (state.kind === "status") {
        app.innerHTML = `<div class="center">
          <section class="panel status">
            <div class="spinner" aria-hidden="true"></div>
            <h1 class="title" style="justify-content: center;"><img class="app-icon" src="/icon-192.png" alt=""><span>Screen Analyser</span></h1>
            <p class="status-text">${escapeHtml(state.message || "Working...")}</p>
          </section>
        </div>`;
        return;
      }

      if (state.kind === "error") {
        const text = `<div class="error-box" dir="auto">${escapeHtml(state.text || "").replace(/\\n/g, "<br>")}</div>`;
        app.innerHTML = resultChrome(
          { ...state, title: state.title || "Screen Analyser - Error", rtl: false },
          `<h1 class="section-title error-title">Error</h1>${text}`,
          "txt"
        );
        return;
      }

      if (state.kind === "raw") {
        const raw = `<div class="raw-text">${escapeHtml(state.text || "")}</div>`;
        app.innerHTML = resultChrome(state, raw, "txt");
        return;
      }

      const cards = parseSections(state.text || "").map((section) => `
        <article class="section-card">
          <h2 class="section-title">${escapeHtml(section.title || "Result")}</h2>
          <div class="section-body">${renderBody(section.body)}</div>
        </article>
      `).join("");
      app.innerHTML = resultChrome(state, `<div class="sections">${cards}</div>`, "md");
    }

    async function refresh() {
      try {
        const response = await fetch(`/api/view/${encodeURIComponent(VIEW_ID)}`, { cache: "no-store" });
        const state = await response.json();
        const fingerprint = JSON.stringify(state);
        if (fingerprint !== currentFingerprint) {
          currentFingerprint = fingerprint;
          render(state);
        }
      } catch (err) {
        render({
          kind: "error",
          title: "Screen Analyser - Error",
          text: "The local browser UI server is not responding.",
          rtl: false,
          screenshot_data_url: ""
        });
      } finally {
        window.setTimeout(refresh, 800);
      }
    }

    refresh();
  </script>
</body>
</html>
"""


_SETTINGS_TEMPLATE = """<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Screen Analyser - Settings</title>
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#0f766e">
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #64748b;
      --line: #d8e0ea;
      --accent: #0f766e;
      --accent-soft: #e7f5f3;
      --danger: #b42318;
      --ok: #137333;
      --shadow: 0 10px 28px rgba(20, 30, 55, 0.10);
    }
    * { box-sizing: border-box; }
    html { overflow-y: scroll; }
    body {
      margin: 0;
      min-height: 100vh;
      overflow-x: hidden;
      overflow-y: scroll;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.5 "Segoe UI", Tahoma, Arial, sans-serif;
    }
    .page {
      width: min(calc(100vw - 36px), var(--app-width, 70vw));
      max-width: 100%;
      margin: 0 auto;
      padding: 18px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
    }
    .settings-layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 36%);
      grid-template-rows: auto auto;
      gap: 14px;
      align-items: start;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      color: var(--accent);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .app-icon {
      width: 28px;
      height: 28px;
      flex: 0 0 auto;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 16px;
      margin-bottom: 0;
    }
    .connection-panel { grid-column: 1; grid-row: 1; }
    .translation-panel { grid-column: 1; grid-row: 2; }
    .models-panel {
      grid-column: 2;
      grid-row: 1 / span 2;
      position: sticky;
      top: 18px;
    }
    .grid {
      display: grid;
      grid-template-columns: 180px minmax(0, 1fr);
      gap: 12px 16px;
      align-items: center;
    }
    label {
      font-weight: 700;
      color: #24324a;
    }
    input, select {
      width: 100%;
      border: 1px solid #c9d4e2;
      border-radius: 6px;
      padding: 9px 10px;
      font: 14px "Segoe UI", Tahoma, Arial, sans-serif;
      color: var(--text);
      background: #fff;
    }
    input.mono {
      font-family: Consolas, "Cascadia Mono", monospace;
    }
    .row {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .row input { flex: 1; }
    button {
      appearance: none;
      border: 1px solid #c9d4e2;
      background: #fff;
      color: #152238;
      border-radius: 6px;
      padding: 9px 12px;
      font: 700 13px "Segoe UI", Tahoma, Arial, sans-serif;
      cursor: pointer;
      white-space: nowrap;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    button:hover { background: #f8fafc; }
    button.primary:hover { background: #0b635c; }
    .icon-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
    }
    .icon {
      width: 16px;
      height: 16px;
      flex: 0 0 auto;
      stroke: currentColor;
      fill: none;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .hint {
      grid-column: 2;
      color: var(--muted);
      font-size: 13px;
      margin-top: -8px;
    }
    .status {
      color: var(--muted);
      font-size: 13px;
      min-height: 20px;
    }
    .status.ok { color: var(--ok); }
    .status.err { color: var(--danger); }
    .model-list {
      display: grid;
      gap: 8px;
      max-height: calc(100vh - 160px);
      min-height: 430px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfdff;
    }
    .model-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      width: 100%;
      text-align: left;
      border: 1px solid #dce4ee;
      background: #fff;
      border-radius: 6px;
      padding: 9px 10px;
      font-family: Consolas, "Cascadia Mono", monospace;
      font-weight: 600;
    }
    .model-item.selected {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: #064b45;
    }
    .empty {
      padding: 10px;
      color: var(--muted);
      background: #fff;
      border-radius: 6px;
      border: 1px dashed #c9d4e2;
    }
    .toggle {
      display: flex;
      gap: 10px;
      align-items: center;
      font-weight: 500;
    }
    .toggle input {
      width: 18px;
      height: 18px;
    }
  </style>
</head>
<body>
  <main class="page">
    <header>
      <h1 class="brand"><img class="app-icon" src="/icon-192.png" alt=""><span>Settings</span></h1>
      <button class="primary icon-btn" type="button" onclick="saveSettings()">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"></path><path d="M17 21v-8H7v8"></path><path d="M7 3v5h8"></path></svg>
        <span>Save settings</span>
      </button>
    </header>

    <div class="settings-layout">
    <section class="panel connection-panel">
      <div class="grid">
        <label for="apiKey">Ollama API token</label>
        <div class="row">
          <input id="apiKey" type="password" autocomplete="off" spellcheck="false">
          <button class="icon-btn" type="button" onclick="toggleToken()">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            <span>Show</span>
          </button>
        </div>
        <div class="hint">Only needed for cloud models from ollama.com. Local models do not need a token.</div>

        <label for="model">Model</label>
        <div class="row">
          <input id="model" class="mono" type="text" spellcheck="false">
          <button class="icon-btn" type="button" onclick="refreshModels()">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 0 1-15.4 6.4L3 16"></path><path d="M3 16v5h5"></path><path d="M3 12A9 9 0 0 1 18.4 5.6L21 8"></path><path d="M21 8V3h-5"></path></svg>
            <span>Refresh models</span>
          </button>
        </div>
        <div class="hint">Available models are always listed below. Click one to use it, or type a custom model name.</div>
      </div>
    </section>

    <section class="panel models-panel">
      <div class="row" style="justify-content: space-between; margin-bottom: 10px;">
        <label>Available models on this device/account</label>
        <span id="modelStatus" class="status"></span>
      </div>
      <div id="modelList" class="model-list">
        <div class="empty">Loading models...</div>
      </div>
    </section>

    <section class="panel translation-panel">
      <div class="grid">
        <label for="fromLang">Translate from</label>
        <select id="fromLang"></select>

        <label for="toLang">Translate to</label>
        <select id="toLang"></select>

        <label>Thinking mode</label>
        <label class="toggle">
          <input id="thinking" type="checkbox">
          Enable model thinking when the selected model supports it
        </label>
      </div>
    </section>
    </div>
  </main>

  <script>
    let settings = null;
    let models = [];
    const ICONS = {
      check: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m20 6-11 11-5-5"></path></svg>',
      plus: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>'
    };

    function setAppWidth() {
      const width = Math.max(900, Math.round(window.screen.availWidth * 0.70));
      document.documentElement.style.setProperty("--app-width", `${width}px`);
    }

    window.addEventListener("resize", setAppWidth);
    setAppWidth();

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[ch]);
    }

    function fillSelect(id, values, selected) {
      const el = document.getElementById(id);
      el.innerHTML = values.map((value) => {
        const isSelected = value === selected ? " selected" : "";
        return `<option value="${escapeHtml(value)}"${isSelected}>${escapeHtml(value)}</option>`;
      }).join("");
    }

    async function loadSettings() {
      const response = await fetch("/api/settings", { cache: "no-store" });
      settings = await response.json();
      document.getElementById("apiKey").value = settings.ollama_api_key || "";
      document.getElementById("model").value = settings.model || "";
      document.getElementById("thinking").checked = Boolean(settings.thinking);
      fillSelect("fromLang", settings.from_languages || [], settings.translate_from);
      fillSelect("toLang", settings.languages || [], settings.translate_to);
      refreshModels();
    }

    function toggleToken() {
      const input = document.getElementById("apiKey");
      input.type = input.type === "password" ? "text" : "password";
    }

    function renderModels() {
      const list = document.getElementById("modelList");
      const current = document.getElementById("model").value;
      if (!models.length) {
        list.innerHTML = `<div class="empty">No models were found. Check that Ollama is running, or add an Ollama cloud token and refresh.</div>`;
        return;
      }
      list.innerHTML = models.map((name) => {
        const selected = name === current ? " selected" : "";
        return `<button type="button" class="model-item${selected}" onclick="chooseModel('${encodeURIComponent(name)}')">
          <span>${escapeHtml(name)}</span>
          <span class="icon-btn">${selected ? ICONS.check : ICONS.plus}<span>${selected ? "Selected" : "Use"}</span></span>
        </button>`;
      }).join("");
    }

    function chooseModel(encodedName) {
      document.getElementById("model").value = decodeURIComponent(encodedName);
      renderModels();
    }

    async function refreshModels() {
      const status = document.getElementById("modelStatus");
      status.className = "status";
      status.textContent = "Fetching...";
      document.getElementById("modelList").innerHTML = `<div class="empty">Loading models...</div>`;
      try {
        const response = await fetch("/api/models", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: document.getElementById("apiKey").value })
        });
        const data = await response.json();
        models = data.models || [];
        status.className = models.length ? "status ok" : "status err";
        status.textContent = models.length ? `${models.length} model(s) found` : "No models found";
        renderModels();
      } catch (err) {
        models = [];
        status.className = "status err";
        status.textContent = "Could not fetch models";
        renderModels();
      }
    }

    async function saveSettings() {
      const payload = {
        ollama_api_key: document.getElementById("apiKey").value,
        model: document.getElementById("model").value,
        thinking: document.getElementById("thinking").checked,
        translate_from: document.getElementById("fromLang").value,
        translate_to: document.getElementById("toLang").value
      };
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      const status = document.getElementById("modelStatus");
      if (data.ok) {
        settings = data.settings;
        status.className = "status ok";
        status.textContent = "Saved";
        renderModels();
      } else {
        status.className = "status err";
        status.textContent = data.error || "Save failed";
      }
    }

    document.getElementById("model").addEventListener("input", renderModels);
    loadSettings();
  </script>
</body>
</html>
"""


_ABOUT_TEMPLATE = """<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Screen Analyser - About</title>
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#0f766e">
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #64748b;
      --line: #d8e0ea;
      --accent: #0f766e;
      --shadow: 0 10px 28px rgba(20, 30, 55, 0.10);
    }
    * { box-sizing: border-box; }
    html { overflow-y: scroll; }
    body {
      margin: 0;
      min-height: 100vh;
      overflow-x: hidden;
      overflow-y: scroll;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.55 "Segoe UI", Tahoma, Arial, sans-serif;
    }
    .page {
      width: min(calc(100vw - 36px), var(--app-width, 70vw));
      max-width: 100%;
      margin: 0 auto;
      padding: 18px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    header {
      padding: 18px;
      border-bottom: 1px solid var(--line);
      background: #fbfdff;
    }
    h1 {
      margin: 0 0 4px;
      color: var(--accent);
      font-size: 22px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 4px;
    }
    .app-icon {
      width: 30px;
      height: 30px;
      flex: 0 0 auto;
    }
    .sub {
      color: var(--muted);
      margin: 0;
    }
    section {
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
    }
    section:last-child { border-bottom: 0; }
    h2 {
      margin: 0 0 12px;
      font-size: 16px;
      color: #123b63;
    }
    .shortcut-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 7px 0;
      border-bottom: 1px solid #edf2f7;
    }
    .shortcut-row:last-child { border-bottom: 0; }
    kbd {
      border: 1px solid #c9d4e2;
      background: #f8fafc;
      border-radius: 6px;
      padding: 4px 7px;
      font: 700 12px Consolas, "Cascadia Mono", monospace;
      color: #123b63;
      white-space: nowrap;
    }
    ul {
      margin: 0;
      padding-inline-start: 22px;
      color: #334155;
    }
    li { margin: 6px 0; }
  </style>
</head>
<body>
  <main class="page">
    <article class="panel">
      <header>
        <h1 class="brand"><img class="app-icon" src="/icon-192.png" alt=""><span>Screen Analyser</span></h1>
        <p class="sub">Capture a screen region and analyse it with Ollama vision models.</p>
      </header>
      <section>
        <h2>Keyboard shortcuts</h2>
        __TASK_ROWS__
        <div class="shortcut-row"><span>Full screen capture</span><kbd>CTRL+ALT+F</kbd></div>
        <div class="shortcut-row"><span>Clipboard image</span><kbd>Tray menu</kbd></div>
      </section>
      <section>
        <h2>Notes</h2>
        <ul>__TIP_ROWS__</ul>
      </section>
    </article>
  </main>
  <script>
    function setAppWidth() {
      const width = Math.max(900, Math.round(window.screen.availWidth * 0.70));
      document.documentElement.style.setProperty("--app-width", `${width}px`);
    }

    window.addEventListener("resize", setAppWidth);
    setAppWidth();
  </script>
</body>
</html>
"""
