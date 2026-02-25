# 📚 eBook Converter — CORE Tool #11

Beautiful desktop eBook converter with batch processing, metadata editing, and cover management. Built with Tauri 2 (Rust + HTML/CSS/JS).

![CORE Tools](https://img.shields.io/badge/CORE-Tool%20%2311-00ff88?style=flat-square)

## Features

- **Batch Conversion** — EPUB ↔ MOBI ↔ PDF ↔ AZW3 ↔ FB2 ↔ TXT ↔ HTML ↔ DOCX
- **Metadata Editor** — Title, author, cover, description, language, series, tags, ISBN
- **Cover Management** — Extract covers, replace covers, visual preview
- **Table of Contents** — Preview TOC from any eBook
- **Drag & Drop** — Drop files directly into the app
- **Progress Tracking** — Real-time progress bars per file
- **Layout Options** — Page size, margins, font size, line height per conversion
- **Dark Theme** — CORE branding with `#00ff88` accent

## Dependencies

### Required

- **[Calibre](https://calibre-ebook.com/)** — The app uses `ebook-convert` and `ebook-meta` CLI tools from Calibre
  - macOS: `brew install calibre`
  - Linux: `sudo apt install calibre`
  - Windows: Download from [calibre-ebook.com](https://calibre-ebook.com/download)
- **Rust** ≥ 1.70
- **Node.js** ≥ 18

### Verify Calibre is installed

```bash
ebook-convert --version
ebook-meta --version
```

## Build

```bash
# Install JS dependencies
npm install

# Development
npm run tauri dev

# Production build
npm run tauri build
```

The built app will be in `src-tauri/target/release/bundle/`.

## Usage

1. **Add books** — Click "Add Files" or drag & drop eBooks into the app
2. **Select format** — Choose target format from the sidebar
3. **Configure options** — Set page size, margins, font size as needed
4. **Convert** — Hit "⚡ Convert All" and watch the progress
5. **Edit metadata** — Select a book, switch to Metadata tab, edit & save
6. **Extract/replace covers** — Use the Metadata tab sidebar buttons

## Supported Formats

| Format | Input | Output |
|--------|-------|--------|
| EPUB   | ✅    | ✅     |
| MOBI   | ✅    | ✅     |
| PDF    | ✅    | ✅     |
| AZW3   | ✅    | ✅     |
| FB2    | ✅    | ✅     |
| TXT    | ✅    | ✅     |
| HTML   | ✅    | ✅     |
| DOCX   | ✅    | ✅     |
| RTF    | ✅    | —      |
| ODT    | ✅    | —      |

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS — dark theme, smooth animations
- **Backend:** Rust (Tauri 2) — wraps Calibre CLI for conversion & metadata
- **Bridge:** Tauri IPC — async commands with event-based progress

## License

MIT
