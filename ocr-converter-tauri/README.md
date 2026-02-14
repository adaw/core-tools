# OCR & PDF Converter (Tauri 2)

**CORE Tool #12** — Desktop OCR and document conversion app built with Tauri 2 (Rust + HTML/CSS/JS).

## Features

- 🔍 **OCR (Image → Text)** — Tesseract-powered OCR with language selection and confidence scoring
- 📄 **PDF → Text** — Extract text from PDF documents using lopdf
- 🖼️ **Image → PDF** — Convert images to PDF with printpdf
- 📦 **Batch OCR** — Process multiple images at once
- 🌍 **12 languages** — English, Czech, German, French, Spanish, Italian, Polish, Russian, Chinese, Japanese, Korean, Arabic
- 📊 **Confidence score** — Visual indicator of OCR accuracy

## Tech Stack

- **Frontend:** HTML/CSS/JS with dark theme (#1a1a2e, #00ff88)
- **Backend:** Rust with Tauri 2 commands
- **OCR:** tesseract crate (Tesseract 5 wrapper)
- **PDF parsing:** lopdf
- **PDF creation:** printpdf 0.8
- **Image processing:** image crate

## UI

Side-by-side layout:
- **Left panel:** File input with drag & drop zone and image preview
- **Right panel:** Extracted text output with copy/save actions

Dark theme with neon green accents.

## Prerequisites

```bash
brew install tesseract pkgconf
# For more languages:
brew install tesseract-lang
```

## Development

```bash
npm install
cargo tauri dev
```

## Build

```bash
cargo tauri build
```

## Project Structure

```
ocr-converter-tauri/
├── src/                    # Frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── styles.css
│   └── main.js
├── src-tauri/              # Rust backend
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/
│   └── src/
│       ├── lib.rs          # Tauri commands (OCR, PDF, conversion)
│       └── main.rs
├── package.json
└── README.md
```
