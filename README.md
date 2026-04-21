# Screen Analyser

A lightweight Windows desktop application that lets you capture any region of your screen and analyse it instantly with a local AI vision model running through [Ollama](https://ollama.com). Everything runs locally — no cloud, no API keys.

---

## Features

- **Region selector** — drag to select any area of the screen
- **Full-screen capture** — capture the entire screen in one hotkey
- **Clipboard image** — analyse an image you already copied
- **Six built-in AI tasks** with dedicated hotkeys
- **Markdown results** rendered as styled section cards with per-section copy buttons
- **Save results** as `.md` / `.txt` and **save screenshots** as `.png` / `.jpg`
- **Analysis history** — last 20 results accessible from the tray menu
- **Toast notifications** — silent clipboard copy for OCR results
- **Settings dialog** — switch models and toggle thinking mode on the fly
- **About & Shortcuts** reference dialog
- Runs entirely in the background as a **system-tray app** — no persistent window

---

## Built-in Tasks

| Task | Hotkey | Output |
|------|--------|--------|
| Describe Screen | `Ctrl+Alt+S` | Markdown section cards |
| Extract Text (OCR) | `Ctrl+Alt+T` | Plain text, auto-copied |
| Translate to English | `Ctrl+Alt+X` | Plain text |
| Explain / Deep-Dive | `Ctrl+Alt+E` | Markdown section cards |
| Find Errors & Fixes | `Ctrl+Alt+D` | Markdown section cards |
| Summarise Document | `Ctrl+Alt+U` | Markdown section cards |
| Full Screen Capture | `Ctrl+Alt+F` | Markdown section cards |

---

## Requirements

- Windows 10 / 11
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- A vision-capable model pulled, e.g.:

```bash
ollama pull qwen3-vl:4b
```

---

## Quick Start

### Option A — Run the pre-built exe

Download `ScreenAnalyser.exe` from [Releases](../../releases) and double-click it. Ollama must be running in the background.

### Option B — Run from source

```bash
# 1. Clone
git clone git@github.com:alihayajneh/ScreenAnalyser.git
cd ScreenAnalyser

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python screen_analyser.pyw
```

### Option C — Build the exe yourself

```bash
venv\Scripts\pyinstaller screen_analyser.spec
# Output: dist\ScreenAnalyser.exe
```

---

## Project Structure

```
ScreenAnalyser/
├── app/
│   ├── __init__.py
│   ├── about.py            # About & Shortcuts dialog
│   ├── capture.py          # Screen/clipboard capture + Ollama worker
│   ├── config.py           # Path helpers, persistent Settings
│   ├── history.py          # In-memory analysis history store
│   ├── main.py             # App entry point, queue dispatcher
│   ├── markdown_renderer.py# Markdown → styled tkinter Text
│   ├── result_window.py    # Spinner → results window
│   ├── selector.py         # Fullscreen drag-to-select overlay
│   ├── settings_dialog.py  # Model + thinking mode settings
│   ├── state.py            # Shared queue and processing lock
│   ├── tasks.py            # Task registry and built-in prompts
│   ├── toast.py            # Auto-dismissing toast notification
│   └── tray.py             # System-tray icon and submenus
├── generate_icon.py        # Script to regenerate icon.ico
├── icon.ico
├── requirements.txt
├── run.bat
├── screen_analyser.pyw     # Launcher
└── screen_analyser.spec    # PyInstaller build spec
```

---

## Adding a New Task

Edit `app/tasks.py` — add a new `Task` entry to `BUILTIN_TASKS`:

```python
Task(
    id          = "my_task",
    name        = "My Task",
    prompt      = "Your prompt here...",
    hotkey      = "ctrl+alt+m",   # optional
    auto_copy   = False,          # True → silently copy result to clipboard
    raw_output  = False,          # True → plain text instead of section cards
)
```

No changes needed anywhere else — the task appears in the tray menu and hotkey is registered automatically.

---

## Settings

Right-click the tray icon → **Settings** to:

- Select any Ollama model installed on your machine (with live refresh)
- Enable **thinking mode** for deeper step-by-step reasoning (qwen3 / deepseek-r1)

Settings are saved to `settings.json` next to the exe.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `ollama` | Ollama Python client |
| `Pillow` | Screen capture, image processing |
| `pystray` | System-tray icon |
| `keyboard` | Global hotkey hooks |
| `pyinstaller` | Build standalone exe |

---

## License

MIT
