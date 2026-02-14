# 📋 Clipboard Manager — CORE Tool #2

Tauri 2 desktop app for clipboard history management. Rust backend + HTML/CSS/JS frontend.

## Features

- **Clipboard monitoring** — automatic capture via polling (arboard)
- **SQLite storage** — persistent history (1000+ entries, rusqlite)
- **Smart categories** — auto-detection: text, link, code, image
- **Search** — real-time full-text search with debounce
- **Pin** — pin important entries (survive clear)
- **Export** — JSON or TXT export
- **Dark UI** — glassmorphism, #1a1a2e/#00ff88 theme, smooth animations

## Tech Stack

| Layer | Tech |
|-------|------|
| Framework | Tauri 2 |
| Backend | Rust (arboard, rusqlite, chrono, sha2) |
| Frontend | HTML/CSS/JS (vanilla, no framework) |
| Storage | SQLite (~/.local/share/clipboard-manager/) |

## Structure

```
clipboard-manager-tauri/
├── ui/                  # Frontend
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src-tauri/
│   ├── src/
│   │   ├── main.rs      # Entry point
│   │   ├── lib.rs       # Tauri commands + clipboard monitor
│   │   └── db.rs        # SQLite database layer
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── capabilities/
└── package.json
```

## Development

```bash
source "$HOME/.cargo/env"
npm install
cargo check --manifest-path src-tauri/Cargo.toml   # verify
npm run tauri dev                                    # run
```

## Tauri Commands

| Command | Description |
|---------|-------------|
| `get_entries` | Fetch entries with search/filter/pagination |
| `toggle_pin` | Pin/unpin an entry |
| `delete_entry` | Delete single entry |
| `clear_all` | Clear all unpinned entries |
| `get_stats` | Get category/pin statistics |
| `export_entries` | Export as JSON or TXT |
| `copy_to_clipboard` | Copy entry back to clipboard |

## License

MIT
