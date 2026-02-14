# PDF Tools — CORE Tool #7

Tauri 2 desktop app for PDF manipulation. Dark theme UI with tab-based workflow.

## Features

| Tab | Function |
|-----|----------|
| **Merge** | Combine multiple PDFs into one, drag & drop reorder |
| **Split** | Split PDF by page ranges (e.g. `1-3`, `4-6`) |
| **Compress** | Reduce file size via stream compression |
| **Convert** | PDF ↔ Images (images→PDF via printpdf) |
| **Rotate** | Rotate specific pages by 90°/180°/270° |
| **Text** | Extract text content from PDF pages |
| **Watermark** | Add text watermark to all pages |
| **Security** | Password protect / remove protection |

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS — dark theme (`#1a1a2e`, `#00ff88`)
- **Backend:** Rust with Tauri 2
- **PDF:** `lopdf` 0.34 (read/write/manipulate) + `printpdf` 0.7 (create from images)
- **Image:** `image` 0.25 for format decoding

## Development

```bash
npm install
npm run dev
```

### Build

```bash
npm run build
```

### Check (no compile)

```bash
cd src-tauri && cargo check
```

## Page Thumbnail Preview

The app provides page dimension info (MediaBox) for thumbnail previews in Split and Rotate tabs.

## Limitations

- **PDF→Image:** Requires a PDF renderer (poppler/mupdf) — not available in pure Rust lopdf
- **Encryption:** lopdf doesn't support writing AES-encrypted PDFs natively
- **Text extraction:** Basic content stream parsing (Tj operators) — complex layouts may need OCR

## Structure

```
pdf-tools-tauri/
├── package.json
├── src/
│   └── index.html          # Frontend UI
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json
    └── src/
        ├── main.rs          # Tauri app entry
        └── pdf_ops.rs       # All PDF operations
```
