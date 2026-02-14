# ◆ CORE Media Converter

**FFmpeg-based Video/Audio Converter with a clean, modern UI.**

Part of the [CORE SYSTEMS](https://github.com/goden-ai/core-tools) tool suite.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## Features

- 🎬 **Video conversion** — MP4, MKV, AVI, MOV
- 🎵 **Audio conversion** — MP3, WAV, FLAC, AAC, OGG
- 📦 **Batch processing** — convert multiple files at once
- 🎯 **Quality presets** — High / Medium / Low (maps to FFmpeg CRF/bitrate)
- 📊 **Real-time progress** — per-file progress bars with time tracking
- 🎨 **Dark theme UI** — CORE SYSTEMS branding with green accents
- 📂 **Drag & drop** support (when TkDND is available)
- 🖥️ **Cross-platform** — Windows, macOS, Linux
- 📦 **Zero Python dependencies** — uses only tkinter (included with Python)

## Screenshot

```
┌─────────────────────────────────────────────────────┐
│  ◆ CORE Media Converter                     v1.0.0  │
│─────────────────────────────────────────────────────│
│                                                     │
│  video_interview.mov        45.2 MB  •  MOV         │
│  Converting… 67%            ████████████░░░░░░      │
│                                                     │
│  podcast_ep12.wav           120.8 MB  •  WAV        │
│  Queued                     ░░░░░░░░░░░░░░░░░░      │
│                                                     │
│  + Add Files                          2 files       │
│─────────────────────────────────────────────────────│
│  Output Format [MP4 ▾]  Quality [Medium ▾]  Output  │
│─────────────────────────────────────────────────────│
│  Converting 1/2…                    [ ▶ Convert ]   │
└─────────────────────────────────────────────────────┘
```

## Requirements

### FFmpeg (Required)

CORE Media Converter is a GUI wrapper around FFmpeg. **You must have FFmpeg installed** on your system.

| Platform | Install Command |
|----------|----------------|
| **macOS** | `brew install ffmpeg` |
| **Windows** | `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html) |
| **Ubuntu/Debian** | `sudo apt install ffmpeg` |
| **Fedora** | `sudo dnf install ffmpeg` |
| **Arch** | `sudo pacman -S ffmpeg` |

The app searches for `ffmpeg` in:
1. Bundled location (PyInstaller builds)
2. Same directory as the executable
3. System PATH

### Python (for running from source)

- Python 3.10+
- tkinter (included with most Python installations)
- No pip packages required

## Usage

### Run from source

```bash
python converter.py
```

### Build standalone executable

**macOS / Linux:**
```bash
chmod +x build.sh
./build.sh
```

**Windows:**
```batch
build.bat
```

The built app will be in the `dist/` directory.

### Build with bundled FFmpeg

To create a fully self-contained build with FFmpeg included:

```bash
# macOS
cp $(which ffmpeg) ./ffmpeg
cp $(which ffprobe) ./ffprobe
./build.sh

# Windows
copy C:\path\to\ffmpeg.exe ffmpeg.exe
copy C:\path\to\ffprobe.exe ffprobe.exe
build.bat
```

The build scripts automatically detect and include `ffmpeg`/`ffprobe` if they exist in the project directory.

## Quality Presets

### Video (H.264)

| Preset | CRF | x264 Preset | Audio Bitrate |
|--------|-----|-------------|---------------|
| High | 18 | slow | 256 kbps |
| Medium | 23 | medium | 192 kbps |
| Low | 28 | fast | 128 kbps |

### Audio

| Preset | MP3 | AAC | FLAC | OGG |
|--------|-----|-----|------|-----|
| High | 320k | 256k | Level 8 | Q8 |
| Medium | 192k | 192k | Level 5 | Q5 |
| Low | 128k | 128k | Level 0 | Q3 |

## Project Structure

```
media-converter/
├── converter.py      # Main application
├── build.sh          # macOS/Linux build script
├── build.bat         # Windows build script
├── requirements.txt  # Build dependencies (PyInstaller only)
└── README.md
```

## License

MIT — Part of CORE SYSTEMS by [goden.ai](https://goden.ai)
