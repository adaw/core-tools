# ⬡ CORE Clipboard Manager

**Clipboard history with search** — part of the [CORE SYSTEMS](https://github.com/adaw/core-tools) tool suite.

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-00ff88?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-macOS%20|%20Windows%20|%20Linux-333?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-00ff88?style=flat-square)

## Features

- **Automatic clipboard monitoring** — captures everything you copy
- **Search & filter** — instant search across your entire history
- **Smart categories** — auto-detects text, links, and images
- **Pin important items** — pinned entries stay at the top and survive cleanup
- **Quick copy** — click any item to copy it back to clipboard
- **Export** — save history as JSON or plain text
- **Persistent storage** — history survives app restarts
- **Dark theme** — CORE SYSTEMS branding with `#00ff88` accents
- **Zero dependencies** — pure Python + tkinter (included with Python)

## Screenshot

```
┌─────────────────────────────────────────────────┐
│ ⬡ CORE  Clipboard Manager       12 items  ● ON │
│─────────────────────────────────────────────────│
│ 🔍 Search clipboard history…                    │
│ ◉ All  ○ 📝 Text  ○ 🔗 Links  ○ 🖼 Images     │
│─────────────────────────────────────────────────│
│ 📌 🔗 14:32 · Feb 14              Copy 📌  ✕   │
│ https://github.com/adaw/core-tools              │
│─────────────────────────────────────────────────│
│ 📝 14:30 · Feb 14                 Copy 📌  ✕   │
│ SELECT * FROM users WHERE active = true;        │
│─────────────────────────────────────────────────│
│ 🔗 14:28 · Feb 14                 Copy 📌  ✕   │
│ https://docs.python.org/3/library/tkinter.html  │
└─────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Run directly
python3 clipboard_manager.py

# Or install dependencies and build (see below)
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl + F` | Focus search |
| `Cmd/Ctrl + E` | Export history |
| `Escape` | Clear search |

## Build

### Requirements

- Python 3.10+
- PyInstaller (`pip install pyinstaller`)

### macOS

```bash
chmod +x build.sh
./build.sh
# Output: dist/CORE Clipboard Manager.app
```

### Windows

```cmd
build.bat
:: Output: dist\CORE Clipboard Manager.exe
```

### Manual Build

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "CORE Clipboard Manager" clipboard_manager.py
```

## Data Storage

History is stored as JSON:

| Platform | Location |
|---|---|
| macOS | `~/Library/Application Support/CORE Clipboard Manager/history.json` |
| Windows | `%APPDATA%\CORE Clipboard Manager\history.json` |
| Linux | `~/.config/core-clipboard-manager/history.json` |

## Limits

- Maximum **1000 unpinned** items (pinned items are unlimited)
- Clipboard polled every **500ms**
- Content preview truncated at **500 characters** in the UI

## License

MIT — part of [CORE SYSTEMS](https://github.com/adaw/core-tools).
