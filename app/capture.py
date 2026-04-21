"""
app/capture.py — Screen capture + Ollama analysis worker.

Public API
──────────
  run_analysis(bbox, task, model, thinking, queue, lock)
      Captures a screen region (bbox) and runs analysis.

  run_analysis_fullscreen(task, model, thinking, queue, lock)
      Captures the entire screen and runs analysis.

  run_analysis_clipboard(task, model, thinking, queue, lock)
      Grabs an image from the clipboard and runs analysis.
      Posts ("error", …) if no image is found on the clipboard.

Queue messages produced
───────────────────────
  ("status",        str)
  ("status_update", str)
  ("result",        (str, PIL.Image, Task))
  ("error",         str)
"""

from __future__ import annotations

import io
import queue as _queue
import re
import threading
from typing import Optional, Tuple

import ollama
from PIL import Image, ImageGrab

from .tasks import Task

BBox = Tuple[int, int, int, int]


def run_analysis(
    bbox:     BBox,
    task:     Task,
    model:    str,
    thinking: bool,
    q:        "_queue.Queue",
    lock:     threading.Event,
) -> None:
    """Spawn the analysis worker thread for a selected region."""
    threading.Thread(
        target  = _worker,
        args    = (bbox, task, model, thinking, q, lock),
        daemon  = True,
        name    = "capture-worker",
    ).start()


def run_analysis_fullscreen(
    task:     Task,
    model:    str,
    thinking: bool,
    q:        "_queue.Queue",
    lock:     threading.Event,
) -> None:
    """Spawn the analysis worker thread for the entire screen (bbox=None)."""
    threading.Thread(
        target  = _worker,
        args    = (None, task, model, thinking, q, lock),
        daemon  = True,
        name    = "capture-worker",
    ).start()


def run_analysis_clipboard(
    task:     Task,
    model:    str,
    thinking: bool,
    q:        "_queue.Queue",
    lock:     threading.Event,
) -> None:
    """Spawn the analysis worker thread using a clipboard image."""
    threading.Thread(
        target  = _clipboard_worker,
        args    = (task, model, thinking, q, lock),
        daemon  = True,
        name    = "capture-worker",
    ).start()


def _run_inference(
    screenshot: Image.Image,
    task:       Task,
    model:      str,
    thinking:   bool,
    q:          "_queue.Queue",
) -> str:
    """
    Send *screenshot* + *task.prompt* to Ollama and return the final content
    string.  Posts ("status_update", …) while waiting.  Raises on error.
    """
    q.put(("status_update", f"{task.name}  ·  {model}…"))

    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    response = ollama.chat(
        model    = model,
        messages = [{"role": "user", "content": task.prompt, "images": [image_bytes]}],
        think    = thinking,
    )

    if hasattr(response, "message"):
        content       = response.message.content or ""
        thinking_text = getattr(response.message, "thinking", None)
    else:
        content       = response["message"]["content"] or ""
        thinking_text = response["message"].get("thinking")

    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    if thinking and thinking_text and thinking_text.strip():
        quoted  = "\n".join(f"> {ln}" for ln in thinking_text.strip().splitlines())
        content = f"### Thinking\n{quoted}\n\n---\n\n{content}"

    return content


def _worker(
    bbox:     Optional[BBox],
    task:     Task,
    model:    str,
    thinking: bool,
    q:        "_queue.Queue",
    lock:     threading.Event,
) -> None:
    try:
        # ── 1. Capture ───────────────────────────────────────────────────────
        if bbox is None:
            q.put(("status", "Capturing full screen…"))
        else:
            q.put(("status", "Capturing region…"))
        screenshot: Image.Image = ImageGrab.grab(bbox=bbox)

        # ── 2. Ollama inference ──────────────────────────────────────────────
        content = _run_inference(screenshot, task, model, thinking, q)
        q.put(("result", (content, screenshot, task)))

    except ollama.ResponseError as exc:
        q.put(("error",
            f"**Ollama error**\n\n{exc}\n\n"
            f"Is the model `{model}` pulled?\n\n"
            f"Run:  `ollama pull {model}`"))

    except ConnectionRefusedError:
        q.put(("error",
            "**Could not connect to Ollama**\n\n"
            "Make sure the daemon is running:\n\n"
            "```\nollama serve\n```"))

    except Exception as exc:                                    # noqa: BLE001
        q.put(("error",
            f"**Unexpected error**\n\n`{type(exc).__name__}`: {exc}"))

    finally:
        lock.clear()


def _clipboard_worker(
    task:     Task,
    model:    str,
    thinking: bool,
    q:        "_queue.Queue",
    lock:     threading.Event,
) -> None:
    try:
        q.put(("status", "Reading clipboard image…"))
        screenshot = ImageGrab.grabclipboard()

        if screenshot is None:
            q.put(("error",
                "**No image on clipboard**\n\n"
                "Copy an image to the clipboard first, then try again."))
            return

        if not isinstance(screenshot, Image.Image):
            q.put(("error",
                "**Clipboard does not contain an image**\n\n"
                "Only image data is supported. Copy an image (e.g. "
                "with Print Screen or from a browser) and try again."))
            return

        content = _run_inference(screenshot, task, model, thinking, q)
        q.put(("result", (content, screenshot, task)))

    except ollama.ResponseError as exc:
        q.put(("error",
            f"**Ollama error**\n\n{exc}\n\n"
            f"Is the model `{model}` pulled?\n\n"
            f"Run:  `ollama pull {model}`"))

    except ConnectionRefusedError:
        q.put(("error",
            "**Could not connect to Ollama**\n\n"
            "Make sure the daemon is running:\n\n"
            "```\nollama serve\n```"))

    except Exception as exc:                                    # noqa: BLE001
        q.put(("error",
            f"**Unexpected error**\n\n`{type(exc).__name__}`: {exc}"))

    finally:
        lock.clear()
