# 🖼️ Image Converter — CORE Tool #4

Batch image converter built with **Tauri 2** (Rust + HTML/CSS/JS). Fast, native, privacy-first — all processing happens locally.

## Features

- **Batch conversion** — PNG, JPEG, WebP, AVIF, BMP, TIFF, ICO, GIF
- **Quality control** — adjustable slider (1-100%)
- **Resize** — by width, height, or both (Lanczos3)
- **Metadata strip** — clean EXIF/metadata on export
- **Thumbnail grid** — visual preview of all loaded images
- **Before/after preview** — click any image to inspect
- **Parallel processing** — powered by Rayon for multi-core speed
- **Dark theme** — #1a1a2e / #00ff88 aesthetic

## Tech Stack

| Layer    | Tech                        |
|----------|-----------------------------|
| Frontend | HTML / CSS / vanilla JS     |
| Backend  | Rust + Tauri 2              |
| Imaging  | `image` crate + `webp`      |
| Parallel | `rayon`                     |

## Project Structure

```
image-converter-tauri/
├── src/                  # Frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── src-tauri/            # Rust backend
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/
│   └── src/
│       ├── main.rs       # Tauri commands
│       └── converter.rs  # Image processing engine
├── package.json
└── README.md
```

## Development

```bash
# Install dependencies
npm install

# Check Rust compilation
cd src-tauri && cargo check

# Run in dev mode
npm run tauri dev

# Build release
npm run tauri build
```

## Tauri Commands

| Command            | Description                            |
|--------------------|----------------------------------------|
| `get_image_info`   | Read dimensions, format, size          |
| `generate_thumbnail` | Create base64 thumbnail for grid     |
| `convert_images`   | Batch convert with options             |

## License

MIT
