# ⏺ CORE Screen Recorder

**Record your screen — no watermarks, no limits, no BS.**

Part of the [CORE SYSTEMS](https://github.com/core-systems) free utility suite.

![Python](https://img.shields.io/badge/Python-3.9+-00ff88?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-00ff88?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Win%20%7C%20macOS%20%7C%20Linux-00ff88?style=flat-square)

---

## Features

- 🖥 **Fullscreen or Region capture** — record everything or just what you need
- 🎯 **FPS control** — 15, 30, or 60 FPS
- 🎤 **Audio recording** — microphone input (system audio with ffmpeg)
- 📦 **Multiple formats** — MP4, MKV, GIF
- ⌨️ **Global hotkeys** — Ctrl+Shift+R to start/stop, Ctrl+Shift+P to pause
- ⏱ **Countdown timer** — 0-5 second delay before recording
- 🖱 **Cursor highlight** — visual indicator around your mouse
- ✂️ **Quick trim** — trim your recording without leaving the app
- 💾 **Auto-save** — recordings saved automatically with timestamps
- 🎨 **Dark theme** — clean modern UI with CORE SYSTEMS branding
- 🚫 **No watermark** — ever

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python screen_recorder.py
```

## Build Standalone

### macOS
```bash
chmod +x build.sh
./build.sh
```

### Windows
```cmd
build.bat
```

Output: `dist/CORE Screen Recorder.app` (macOS) or `dist/CORE Screen Recorder.exe` (Windows)

## Dependencies

| Package | Purpose |
|---------|---------|
| `mss` | Fast cross-platform screen capture |
| `opencv-python` | Video encoding (MP4, MKV) |
| `numpy` | Frame processing |
| `Pillow` | GIF export, image handling |
| `pynput` | Global hotkey support |
| `pyaudio` | Microphone recording |
| `ffmpeg` | Audio muxing (optional, for system audio) |

## Hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+R` | Start / Stop recording |
| `Ctrl+Shift+P` | Pause / Resume |

## Configuration

Settings are auto-saved to `~/.core-screen-recorder.json` and restored on launch.

## License

MIT — free for personal and commercial use.

---

**CORE SYSTEMS** — Tools that work. No bloat. No tracking. No watermarks.
