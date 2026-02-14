# ⬡ CORE Duplicate Finder

**Find and remove duplicate files.** Part of the CORE SYSTEMS tools suite.

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Multiple detection methods:** SHA-256, MD5, Size+Name matching
- **Perceptual hash** for similar images (optional, requires `Pillow` + `imagehash`)
- **Multi-threaded scanning** with size pre-filter for speed
- **Smart auto-select:** keep newest, oldest, or shortest path
- **Dry run mode** — preview what would be deleted
- **Trash support** — move to Trash instead of permanent deletion (requires `send2trash`)
- **Filters:** by file type, size range, date range
- **Export reports** as JSON or plain text
- **Statistics** — see how much space you'll reclaim
- **Dark theme UI** with CORE SYSTEMS branding

## Quick Start

```bash
# Run directly
python3 finder.py

# Or install optional dependencies for full features
pip3 install Pillow imagehash send2trash
python3 finder.py
```

## Build Standalone

### macOS
```bash
chmod +x build.sh
./build.sh
# → dist/CORE Duplicate Finder.app
```

### Windows
```cmd
build.bat
REM → dist\CORE Duplicate Finder.exe
```

## Usage

1. **Add folders** to scan using the "+ Add Folder" button
2. **Choose detection method** (SHA-256 recommended for accuracy)
3. **Set filters** (optional): file extensions, size range
4. Click **⬡ SCAN FOR DUPLICATES**
5. **Review results** — double-click files to mark/unmark for deletion
6. Use **Auto-select** to quickly pick which copies to keep
7. **Delete** marked files or **Export** a report

## Detection Methods

| Method | Speed | Accuracy | Best For |
|--------|-------|----------|----------|
| SHA-256 | Medium | Exact | General use |
| MD5 | Fast | Exact (less secure) | Large collections |
| Size+Name | Fastest | Approximate | Quick overview |
| Perceptual Hash | Slow | Similar images | Photo libraries |

## Dependencies

- **Required:** Python 3.8+, tkinter (included with Python)
- **Optional:**
  - `Pillow` + `imagehash` — perceptual image hashing
  - `send2trash` — safe deletion to system Trash

## Part of CORE SYSTEMS

Built by **CORE SYSTEMS** — tools that just work.
