# ⚡ Batch File Renamer

**CORE Tool #1** — Tauri 2 desktop app (Rust + HTML/CSS/JS)

## Features

- 📁 Load files from any directory
- 🔄 **6 rename modes:** Find & Replace, Numbering, Date prefix/suffix, Extension change, Case conversion, Regex
- 👁️ **Live preview** with diff highlighting
- ↩️ **Undo** — revert last rename operation
- 📊 **Progress bar** during rename
- 🌙 **Dark theme** — #1a1a2e + #00ff88 green accent

## Tech Stack

- **Backend:** Rust (Tauri 2)
- **Frontend:** Vanilla HTML/CSS/JS
- **Dependencies:** chrono, regex, serde

## Development

```bash
source "$HOME/.cargo/env"
npm install
npm run tauri dev
```

## Build

```bash
npm run tauri build
```

## Architecture

```
batch-renamer-tauri/
├── src/                  # Frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src-tauri/            # Rust backend
│   ├── src/main.rs       # Tauri commands
│   ├── Cargo.toml
│   └── tauri.conf.json
└── README.md
```

## Tauri Commands

| Command | Description |
|---------|-------------|
| `list_files` | List files in a directory |
| `preview_rename` | Preview rename results with diff |
| `execute_rename` | Execute batch rename |
| `undo_rename` | Undo last rename operation |
| `get_undo_count` | Get number of undoable operations |
