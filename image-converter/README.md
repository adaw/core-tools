# ⬡ CORE Image Converter

**Batch image format converter** — part of the [CORE SYSTEMS](https://github.com/core-systems) free utility suite.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)

## Features

- **Batch conversion** — convert hundreds of images at once
- **Format support** — PNG, JPG/JPEG, WebP, AVIF*, BMP, TIFF, ICO
- **Resize** — optional width × height resize with Lanczos resampling
- **Quality control** — slider for lossy formats (JPEG, WebP, AVIF)
- **Metadata stripping** — remove EXIF and other metadata for privacy
- **Live preview** — click any file to preview before converting
- **Drag & drop** — drop files/folders directly into the app (requires tkinterdnd2)
- **Dark theme** — modern UI with CORE SYSTEMS branding
- **Zero cloud** — everything runs locally, your images never leave your machine

*\*AVIF support requires `pillow-avif-plugin` or Pillow 10.1+*

## Quick Start

### Run from source

```bash
# Install dependency
pip install Pillow

# Optional: drag & drop support + AVIF
pip install tkinterdnd2 pillow-avif-plugin

# Run
python image_converter.py
```

### Build standalone app

**macOS:**
```bash
chmod +x build.sh
./build.sh
# Output: dist/CORE Image Converter.app
```

**Windows:**
```cmd
build.bat
REM Output: dist\CORE Image Converter.exe
```

## Usage

1. **Add files** — drag & drop images or click "Add Files" / "Add Folder"
2. **Choose format** — select target format from the dropdown
3. **Adjust options** — quality, resize, metadata stripping
4. **Set output directory** — or leave as "(same as source)"
5. **Click Convert All** — watch the progress bar

## Supported Formats

| Format | Read | Write | Lossy Quality |
|--------|------|-------|---------------|
| PNG    | ✓    | ✓     | —             |
| JPEG   | ✓    | ✓     | ✓             |
| WebP   | ✓    | ✓     | ✓             |
| AVIF   | ✓*   | ✓*    | ✓             |
| BMP    | ✓    | ✓     | —             |
| TIFF   | ✓    | ✓     | —             |
| ICO    | ✓    | ✓     | —             |
| GIF    | ✓    | —     | —             |

## Requirements

- Python 3.9+
- Pillow ≥ 10.0
- tkinter (included with Python)
- *Optional:* tkinterdnd2 (native drag & drop), pillow-avif-plugin (AVIF support)

## License

MIT — free for personal and commercial use.

---

**CORE SYSTEMS** — Free tools, no bullshit.
