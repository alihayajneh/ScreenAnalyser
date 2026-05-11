# Screen Analyser

A lightweight Windows desktop application that lets you capture any region of your screen and analyse it instantly with an AI vision model through [Ollama](https://ollama.com). It supports local Ollama models and optional authenticated Ollama cloud models.

![Screen Analyser app screenshot](screenshot_1.png)

---

## Latest Updates

- Added a cleaned-up browser Settings page with separate Ollama, Translation, and Custom tasks panels.
- Changed available Ollama models to a dropdown list populated from detected local and authenticated cloud models.
- Added custom task support through `tasks.json`, including Settings-based create/edit/delete and automatic tray menu refresh.
- Added a ready-to-use `tasks.json` pack with 15 custom tasks across UI/UX, code review, security, data, finance, legal, medical, academic, meetings, support, sales, project management, product comparison, accessibility, and language learning.
- Fixed hotkey re-registration on devices where the `keyboard` package crashes inside `unhook_all_hotkeys()`.

---

## Version 0.2 - Major Fixes

Version 0.2 is a major stability and usability update focused on the issues found while testing across different Windows devices:

- Replaced the old Tkinter result/settings/about surfaces with a browser-rendered app UI for more consistent layout and text rendering.
- Fixed RTL translation display for Arabic, Hebrew, Persian, Urdu, and other right-to-left outputs by relying on browser text layout instead of Tkinter text widgets.
- Added robust Ollama model discovery with clear fallback behavior when the configured default model is not available.
- Added Ollama API token support so authenticated cloud models can be used from Settings.
- Fixed screenshot/capture flow regressions where capturing could silently do nothing.
- Reworked progress feedback into a small persistent popup that stays visible until results or errors are ready.
- Updated result windows to open as a fixed 70% screen-width app-style window with no horizontal scrolling and reliable vertical scrolling.
- Added browser app identity support, including app icons, favicon, manifest, and native-style save/download actions.

---

## Features

- **Region selector** — drag to select any area of the screen
- **Full-screen capture** — capture the entire screen in one hotkey
- **Clipboard image** — analyse an image you already copied
- **Six built-in AI tasks** with dedicated hotkeys
- **Custom tasks** loaded from `tasks.json`, editable from Settings, and shown in the tray menu
- **Ready task pack** with 15 practical task templates across different domains
- **Browser-rendered results** for consistent rich text, markdown, and RTL layout
- **Save results** as `.md` / `.txt` and **save screenshots** as `.png`
- **Analysis history** — last 20 results accessible from the tray menu
- **Persistent progress popup** while capture/model processing is running
- **Toast notifications** for completed clipboard copy actions
- **Settings page** — choose models from a live dropdown, add an Ollama API token, configure translation, toggle thinking mode, and manage custom tasks
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

## Ready Custom Task Pack

The repository includes [tasks.json](tasks.json) with 15 ready custom tasks:

- UI/UX Review
- Code Review
- Security & Privacy Scan
- Data & Chart Insights
- Finance: Invoice/Receipt Extractor
- Legal: Clause Scanner
- Medical: Note Summarizer
- Academic Paper Digest
- Meeting Notes: Action Items
- Customer Support Reply
- Sales/CRM Brief
- Project Risk Scan
- Product Comparison
- Accessibility Audit
- Language Learning Explainer

When running from source, the app reads `tasks.json` from the project root. When running the compiled exe, place `tasks.json` next to `ScreenAnalyser.exe`.

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

Use **Settings -> Custom tasks** to create or edit tasks. The app writes them to `tasks.json`:

```json
{
  "id": "my_task",
  "name": "My Task",
  "description": "What this task does",
  "hotkey": "ctrl+alt+m",
  "auto_copy": false,
  "raw_output": false,
  "rtl": false,
  "prompt": "Your prompt here..."
}
```

No code changes are needed. The task appears in the tray menu and its hotkey is registered automatically. Built-in tasks still live in `app/tasks.py`.

---

## Settings

Right-click the tray icon → **Settings** to:

- Select any Ollama model installed on your machine (with live refresh)
- Choose available models from a dropdown list
- Add an Ollama API token for authenticated cloud models
- Configure translation source/target languages
- Enable **thinking mode** for deeper step-by-step reasoning (qwen3 / deepseek-r1)
- Create, edit, and delete custom tasks

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
