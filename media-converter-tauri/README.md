# Media Converter (Tauri 2)

**CORE Tool #3** — Batch media converter with real-time progress tracking.

![Tauri 2](https://img.shields.io/badge/Tauri-2.x-blue) ![Rust](https://img.shields.io/badge/Rust-Backend-orange) ![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green)

## Features

- **Drag & drop** file input with animated drop zone
- **Batch conversion** — convert multiple files at once
- **10+ formats**: MP4, MKV, AVI, MOV, WebM, MP3, WAV, FLAC, AAC, OGG
- **Quality presets**: Low, Medium, High, Lossless
- **Real-time progress** with percentage tracking
- **Cancel** running conversions
- **Dark theme** UI (#1a1a2e / #00ff88)

## Prerequisites

- [Rust](https://rustup.rs/) (1.70+)
- [Node.js](https://nodejs.org/) (18+)
- [FFmpeg](https://ffmpeg.org/) in PATH
- Tauri 2 CLI: `cargo install tauri-cli --version "^2"`

## Setup

```bash
npm install
cargo tauri dev
```

## Architecture

```
media-converter-tauri/
├── ui/                  # Frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src-tauri/
│   ├── src/
│   │   ├── lib.rs       # FFmpeg process management, Tauri commands
│   │   └── main.rs      # Entry point
│   ├── Cargo.toml
│   └── tauri.conf.json
└── package.json
```

## Tauri Commands

| Command | Description |
|---------|-------------|
| `start_conversion` | Start FFmpeg conversion job |
| `get_jobs` | Get all job statuses + progress |
| `cancel_job` | Cancel a running conversion |
| `clear_completed` | Remove finished/failed jobs |
| `get_supported_formats` | List supported formats |

## How It Works

1. User drops files → frontend calls `start_conversion` for each
2. Rust spawns FFmpeg as child process with stderr piped
3. Progress parsed from FFmpeg's `time=` output vs total `Duration:`
4. Frontend polls `get_jobs` every 500ms to update progress bars
5. Cancel sets a flag → next loop iteration kills the FFmpeg process
