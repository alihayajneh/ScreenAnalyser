"""
app/browser_preview.py - Browser-backed previews for text that needs real
HTML/CSS layout.

Tk's Text widget is weak for mixed RTL/LTR content. For RTL translations we
write a small local HTML document and open it in a browser engine, which handles
Arabic shaping, bidi ordering, wrapping, and embedded Latin tokens correctly.
"""

from __future__ import annotations

import base64
import html
import json
import os
import shutil
import subprocess
import time
import webbrowser
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

from .config import writable_path


def _preview_dir() -> Path:
    path = writable_path("browser_previews")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cleanup_old_previews(max_files: int = 20) -> None:
    try:
        files = sorted(
            _preview_dir().glob("rtl_preview_*.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in files[max_files:]:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def _image_data_url(image: Optional[Image.Image]) -> str:
    if image is None:
        return ""

    buf = BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _edge_path() -> str | None:
    found = shutil.which("msedge")
    if found:
        return found

    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LocalAppData", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _html_document(title: str, text: str, screenshot: Optional[Image.Image]) -> str:
    image_url = _image_data_url(screenshot)
    escaped_title = html.escape(title)
    escaped_text = html.escape(text)
    text_json = json.dumps(text, ensure_ascii=False)
    image_block = ""
    if image_url:
        image_block = f"""
        <aside class="shot">
          <div class="shot-title">Captured Region</div>
          <img src="{image_url}" alt="Captured region">
        </aside>
        """

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --text: #111827;
      --muted: #64748b;
      --line: #d9e0e8;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Tahoma, "Segoe UI", Arial, sans-serif;
      direction: rtl;
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 32vw);
      gap: 18px;
      padding: 18px;
      max-width: 1280px;
      margin: 0 auto;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-width: 0;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }}
    .toolbar {{
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
    }}
    h1 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.4;
      color: var(--accent);
    }}
    button {{
      appearance: none;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #0f172a;
      padding: 7px 12px;
      border-radius: 6px;
      font: 13px "Segoe UI", Tahoma, sans-serif;
      cursor: pointer;
    }}
    button:hover {{ background: #f8fafc; }}
    .text {{
      padding: 20px 24px 28px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      direction: rtl;
      unicode-bidi: plaintext;
      text-align: right;
      font-size: 18px;
      line-height: 1.9;
    }}
    .text :lang(en), .ltr {{
      direction: ltr;
      unicode-bidi: isolate;
    }}
    .shot {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      align-self: start;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }}
    .shot-title {{
      font: 600 13px "Segoe UI", Tahoma, sans-serif;
      color: var(--muted);
      margin-bottom: 10px;
      text-align: left;
      direction: ltr;
    }}
    .shot img {{
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #eef2f7;
    }}
    @media (max-width: 900px) {{
      .shell {{ grid-template-columns: 1fr; padding: 12px; }}
      .text {{ font-size: 17px; padding: 16px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="panel">
      <div class="toolbar">
        <h1>{escaped_title}</h1>
        <button type="button" onclick="copyText()">Copy text</button>
      </div>
      <div class="text" dir="rtl">{escaped_text}</div>
    </section>
    {image_block}
  </main>
  <script>
    const RESULT_TEXT = {text_json};
    async function copyText() {{
      try {{
        await navigator.clipboard.writeText(RESULT_TEXT);
      }} catch (err) {{
        const area = document.createElement("textarea");
        area.value = RESULT_TEXT;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }}
    }}
  </script>
</body>
</html>
"""


def create_rtl_preview(title: str, text: str, screenshot: Optional[Image.Image]) -> Path:
    _cleanup_old_previews()
    path = _preview_dir() / f"rtl_preview_{int(time.time() * 1000)}.html"
    path.write_text(_html_document(title, text, screenshot), encoding="utf-8")
    return path


def open_preview(path: Path) -> bool:
    url = path.resolve().as_uri()
    edge = _edge_path()
    if edge:
        try:
            subprocess.Popen(
                [edge, f"--app={url}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return True
        except Exception:
            pass

    try:
        return webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        return False
