# CORE OCR & PDF↔Word Converter

**CORE Tool #12** — OCR engine + document conversion suite built with Tauri 2.

Dark theme UI with #00ff88 CORE branding. Drag & drop, batch processing, confidence scores.

## Features

- **🔍 OCR:** Image/scan → text via Tesseract. Multi-language (CZ, EN, DE, FR, …). Batch mode.
- **📝 PDF → Word:** Extract text + layout → DOCX. Image-based PDFs → OCR → DOCX.
- **📄 Word → PDF:** DOCX → PDF conversion via LibreOffice.
- **📋 PDF → Text:** Plain text export with layout preservation.
- **🖼 Image → PDF:** Combine multiple images into multi-page PDF.
- **📊 Confidence scores** for OCR results.
- **⚡ Batch processing** with progress indication.

## Dependencies

Install before running:

```bash
# macOS (Homebrew)
brew install tesseract tesseract-lang poppler libreoffice img2pdf

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-ces tesseract-ocr-deu \
  poppler-utils libreoffice img2pdf
```

| Tool | Purpose |
|------|---------|
| **Tesseract** | OCR engine |
| **Poppler** (pdftotext, pdftoppm) | PDF text extraction & page rendering |
| **LibreOffice** (soffice) | PDF↔DOCX conversion |
| **img2pdf** / ImageMagick | Image → PDF merging |

## Build

```bash
source "$HOME/.cargo/env"

# Install frontend deps
npm install

# Dev mode
npx tauri dev

# Production build
npx tauri build
```

## Tech Stack

- **Backend:** Rust (Tauri 2) — wraps CLI tools (Tesseract, Poppler, LibreOffice)
- **Frontend:** HTML/CSS/JS — no framework, vanilla
- **UI:** CORE dark theme (#0a0a0f bg, #00ff88 accent)
