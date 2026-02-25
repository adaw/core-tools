# CORE Audio Converter & Editor

Desktop audio converter and editor built with **Tauri 2** (Rust + HTML/CSS/JS).

## Features

- **Format Conversion:** MP3 ↔ WAV ↔ FLAC ↔ AAC ↔ OGG ↔ WMA ↔ AIFF ↔ M4A
- **Batch Conversion:** Convert multiple files at once
- **Audio Editing:** Trim/cut, fade in/out, normalize volume, merge files
- **Metadata Editor:** ID3 tags — title, artist, album, year, genre
- **Waveform Visualization:** Interactive display with zoom and selection
- **Playback:** Built-in audio preview with transport controls
- **Configurable:** Bitrate, sample rate, channels
- **Drag & Drop** support

## Requirements

- [Rust](https://rustup.rs/) (1.77+)
- [Node.js](https://nodejs.org/) (18+)
- [FFmpeg](https://ffmpeg.org/) installed and in PATH
- Tauri CLI: `npm install -g @tauri-apps/cli`

## Build & Run

```bash
# Install dependencies
npm install

# Development
npm run tauri dev

# Production build
npm run tauri build
```

## Tech Stack

- **Backend:** Rust + Tauri 2, FFmpeg for audio processing
- **Frontend:** Vanilla HTML/CSS/JS, Web Audio API for waveform & playback
- **UI:** Dark theme with #00ff88 CORE branding

## Architecture

- `src-tauri/src/lib.rs` — Rust commands: probe, convert, edit, merge, metadata, waveform extraction
- `src/app.js` — Frontend logic, Web Audio playback, waveform rendering
- `src/styles.css` — Dark theme UI
- FFmpeg handles all audio processing (conversion, editing, metadata)
