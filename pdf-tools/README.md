# ◆ CORE SYSTEMS — PDF Tools

All-in-one PDF toolkit with a modern dark GUI.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## Features

| Feature | Description |
|---------|-------------|
| **Merge** | Combine multiple PDFs into one, reorder via drag & drop |
| **Split** | Split by individual pages or custom range (e.g. `1-3,5,7-10`) |
| **Compress** | Reduce file size with adjustable quality slider |
| **PDF → Images** | Export pages as PNG/JPEG |
| **Images → PDF** | Convert image files into a single PDF |
| **Rotate** | Rotate pages by 90°/180°/270° (all or selected) |
| **Extract Text** | Pull text from PDF pages, display or save as .txt |
| **Watermark** | Add diagonal text watermark with adjustable opacity & size |
| **Encrypt** | Password-protect PDF (AES-256 via pikepdf) |
| **Decrypt** | Remove password protection |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python pdf_tools.py
```

## Build Standalone

**macOS / Linux:**
```bash
chmod +x build.sh
./build.sh
```

**Windows:**
```cmd
build.bat
```

Output: `dist/PDF Tools` (.app on macOS, .exe on Windows)

## Dependencies

- **PyPDF2** — merge, split, rotate, text extraction
- **pikepdf** — compression, encryption/decryption
- **Pillow** — image conversion
- **reportlab** — watermark generation
- **PyInstaller** — standalone builds

Optional: `pdf2image` + Poppler for full PDF→image page rendering.

## UI

Dark theme with CORE SYSTEMS branding (accent: `#00ff88`). Tabbed interface — one tab per function.

---

*Part of the CORE SYSTEMS toolkit.*
