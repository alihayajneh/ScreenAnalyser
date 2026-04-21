"""
app/tasks.py — Task registry.

A Task defines a single analysis mode:  what prompt to send, how to display
the result, and whether to copy it automatically.

Adding a new task
─────────────────
1.  Write your prompt string below.
2.  Create a Task() entry in BUILTIN_TASKS.
3.  That's it.  The tray menu, hotkey registration, and result routing are
    all driven from this registry automatically.

Display modes
─────────────
  raw_output=False (default)   Result is parsed as Markdown → section cards.
  raw_output=True              Result is shown as plain pre-formatted text
                               (best for OCR / translation output).

Auto-copy
─────────
  auto_copy=True               Full result text is silently copied to the
                               clipboard; a toast notification confirms it.
                               The result window still opens so the user
                               can review what was copied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
#  Prompts
# ─────────────────────────────────────────────────────────────────────────────

_DESCRIBE_PROMPT = (
    "You are a concise screen-reading assistant. "
    "Analyse this screenshot and respond with EXACTLY these three markdown sections "
    "(use ## for each heading, keep them in this order):\n\n"
    "## What's on Screen\n"
    "2–3 bullets: apps, windows, or content that is visible.\n\n"
    "## What's Happening\n"
    "2–3 bullets: the apparent task or activity in progress.\n\n"
    "## Notable Details\n"
    "1–3 bullets: errors, warnings, code, file paths, or anything worth highlighting. "
    "Write N/A as a single bullet if nothing notable.\n\n"
    "Rules: use **bold** for app/tool names, `backticks` for code/paths/commands. "
    "No introductions. No closing remarks. Be brief."
)

_OCR_PROMPT = (
    "Extract ALL text visible in this image exactly as it appears. "
    "Preserve line breaks, indentation, and the original layout as closely as possible. "
    "Output ONLY the raw extracted text — no explanations, no markdown formatting, "
    "no commentary, no surrounding quotes. "
    "If no text is visible, output exactly: (no text found)"
)

_TRANSLATE_PROMPT = (
    "Translate ALL visible text in this image to English. "
    "Preserve the original structure, line breaks, and layout. "
    "Output ONLY the translated text — no explanations or commentary. "
    "If the text is already in English, output it unchanged."
)

# ── Translation language support ──────────────────────────────────────────────

#: Full list shown in the Settings "Translate To" dropdown (alphabetical).
LANGUAGES: list[str] = [
    "Arabic", "Bengali", "Chinese (Simplified)", "Chinese (Traditional)",
    "Dutch", "English", "French", "German", "Greek",
    "Hebrew", "Hindi", "Indonesian", "Italian",
    "Japanese", "Korean", "Malay", "Persian",
    "Polish", "Portuguese", "Russian", "Spanish",
    "Swedish", "Thai", "Turkish", "Ukrainian", "Urdu",
    "Vietnamese",
]

#: Languages whose scripts run right-to-left.
RTL_LANGUAGES: set[str] = {"Arabic", "Hebrew", "Persian", "Urdu", "Pashto"}


def make_translate_prompt(from_lang: str, to_lang: str) -> str:
    """Build a translation prompt for the given language pair."""
    if from_lang == "Auto-detect":
        source = "all visible text in this image"
    else:
        source = f"all {from_lang} text visible in this image"
    return (
        f"Translate {source} to {to_lang}. "
        "Preserve the original structure, line breaks, and paragraph layout. "
        "Output ONLY the translated text — no explanations, no labels, no commentary. "
        f"If the text is already in {to_lang}, output it unchanged."
    )

_EXPLAIN_PROMPT = (
    "You are a helpful assistant. Give a clear, detailed explanation of this screenshot. "
    "Use EXACTLY these three markdown sections:\n\n"
    "## Context\n"
    "What application, tool, or environment is shown, and who would typically use it.\n\n"
    "## What's Happening\n"
    "A step-by-step or point-by-point explanation of what the user is doing or what the screen shows.\n\n"
    "## Key Points\n"
    "Important terms, settings, values, or actions the user should be aware of.\n\n"
    "Use **bold** for technical terms, `backticks` for code/commands. Be thorough but clear."
)

_ERRORS_PROMPT = (
    "You are a debugging assistant. Examine this screenshot for problems. "
    "Use EXACTLY these two markdown sections:\n\n"
    "## Issues Found\n"
    "List each error, warning, exception, failed test, or suspicious value as a bullet. "
    "Include the exact message text if visible. Write 'None visible' if nothing is wrong.\n\n"
    "## Suggested Fixes\n"
    "For each issue above, give a concrete, actionable fix as a bullet. "
    "Use `backticks` for commands, file paths, and code. Be specific."
)

_SUMMARISE_PROMPT = (
    "Summarise the document, article, or content visible in this screenshot. "
    "Use EXACTLY these three markdown sections:\n\n"
    "## Topic\n"
    "One sentence: what this content is about.\n\n"
    "## Key Points\n"
    "3–6 bullets covering the most important ideas, facts, or arguments.\n\n"
    "## Notable Data\n"
    "Any important numbers, dates, names, or statistics worth remembering. "
    "Write N/A if none are visible.\n\n"
    "Use **bold** for key terms. Be concise."
)


# ─────────────────────────────────────────────────────────────────────────────
#  Task dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    id:          str
    name:        str            # displayed in tray menu + result window title
    prompt:      str            # sent verbatim to the model
    description: str = ""      # shown as a tooltip / in settings
    hotkey:      Optional[str] = None   # e.g. "ctrl+alt+s" — None = tray only
    auto_copy:   bool = False   # copy result to clipboard automatically
    raw_output:  bool = False   # display plain text instead of section cards
    rtl:         bool = False   # right-to-left output (Arabic, Hebrew, …)


# ─────────────────────────────────────────────────────────────────────────────
#  Built-in task registry
# ─────────────────────────────────────────────────────────────────────────────
#  Keys are stable IDs used for settings persistence.
#  Order determines the tray menu order.

BUILTIN_TASKS: dict[str, Task] = {
    "describe": Task(
        id          = "describe",
        name        = "Describe Screen",
        prompt      = _DESCRIBE_PROMPT,
        description = "Structured overview: what's visible, what's happening, notable details.",
        hotkey      = "ctrl+alt+s",
    ),
    "ocr": Task(
        id          = "ocr",
        name        = "Extract Text  (OCR)",
        prompt      = _OCR_PROMPT,
        description = "Extract all visible text verbatim.  Result is copied to clipboard automatically.",
        hotkey      = "ctrl+alt+t",
        auto_copy   = True,
        raw_output  = True,
    ),
    "translate": Task(
        id          = "translate",
        name        = "Translate",
        prompt      = _TRANSLATE_PROMPT,   # overridden at runtime from Settings
        description = "Translate visible text between any two languages (set in Settings).",
        hotkey      = "ctrl+alt+x",
        raw_output  = True,
    ),
    "explain": Task(
        id          = "explain",
        name        = "Explain / Deep-Dive",
        prompt      = _EXPLAIN_PROMPT,
        description = "Detailed explanation of the screen context and what is happening.",
        hotkey      = "ctrl+alt+e",
    ),
    "errors": Task(
        id          = "errors",
        name        = "Find Errors & Fixes",
        prompt      = _ERRORS_PROMPT,
        description = "Identify errors, warnings, or bugs and suggest fixes.",
        hotkey      = "ctrl+alt+d",
    ),
    "summarise": Task(
        id          = "summarise",
        name        = "Summarise Document",
        prompt      = _SUMMARISE_PROMPT,
        description = "Extract the topic, key points, and notable data from visible content.",
        hotkey      = "ctrl+alt+u",
    ),
}


def get(task_id: str) -> Task:
    """Return a Task by ID, falling back to 'describe' if unknown."""
    return BUILTIN_TASKS.get(task_id, BUILTIN_TASKS["describe"])
