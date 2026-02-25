# ⚡ CORE Flasher

**USB Bootable Disk Creator** — Better than balenaEtcher. Free, no bloat.

CORE Tool #14 | Part of [CORE Tools](https://github.com/horzenberger/core-tools)

## Features

- **Simple 3-step wizard:** Select Image → Select Drive → Flash
- **Supported formats:** ISO, IMG, DMG, ZIP (auto-extract)
- **Verification:** SHA256/MD5 hash check, byte-by-byte write verification
- **Smart drive detection:** Auto-detects USB drives, shows size/label
- **Safety first:** System disks are NEVER shown — impossible to flash your boot drive
- **Real-time progress:** Speed (MB/s), ETA, animated progress circle
- **Cross-platform:** macOS, Linux, Windows

## Tech Stack

- **Backend:** Rust (Tauri 2) — direct block device writes, zero overhead
- **Frontend:** Vanilla HTML/CSS/JS — dark theme, #00ff88 CORE branding
- **No Electron, no Chromium bundling bloat**

## Build

### Prerequisites

- [Rust](https://rustup.rs/) (stable)
- [Tauri CLI](https://tauri.app/): `cargo install tauri-cli --version "^2"`
- macOS: Xcode Command Line Tools
- Linux: `libwebkit2gtk-4.1-dev`, `libappindicator3-dev`
- Windows: WebView2 (comes with Windows 11)

### Development

```bash
source "$HOME/.cargo/env"
cd core-flasher
cargo tauri dev
```

### Build Release

```bash
cargo tauri build
```

Binary will be in `src-tauri/target/release/`.

## Safety

- System/internal disks are filtered out and never displayed
- External drives are detected via OS-native APIs (diskutil/lsblk/PowerShell)
- Double confirmation dialog before any write operation
- Write verification (byte-by-byte) enabled by default
- Cancel button available at any time during flash

## Architecture

```
core-flasher/
├── src/                  # Frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src-tauri/            # Backend (Rust)
│   ├── src/
│   │   ├── lib.rs        # Tauri commands & app setup
│   │   ├── main.rs       # Entry point
│   │   ├── drives.rs     # OS-native USB drive detection
│   │   └── flasher.rs    # Flash engine, verification, hashing
│   ├── Cargo.toml
│   └── tauri.conf.json
└── README.md
```

## License

MIT
