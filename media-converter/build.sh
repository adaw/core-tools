#!/usr/bin/env bash
# CORE Media Converter — macOS/Linux Build Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "◆ CORE Media Converter — Build"
echo "================================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Please install Python 3.10+."
    exit 1
fi

# Install PyInstaller if needed
if ! python3 -m PyInstaller --version &>/dev/null 2>&1; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Build args
EXTRA_ARGS=()

# Bundle FFmpeg if present locally
if [ -f "./ffmpeg" ]; then
    echo "Found local ffmpeg — bundling."
    EXTRA_ARGS+=(--add-binary "./ffmpeg:.")
fi
if [ -f "./ffprobe" ]; then
    echo "Found local ffprobe — bundling."
    EXTRA_ARGS+=(--add-binary "./ffprobe:.")
fi

# Determine platform-specific options
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Building macOS .app bundle..."
    python3 -m PyInstaller \
        --name "CORE Media Converter" \
        --windowed \
        --onefile \
        --clean \
        --noconfirm \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}" \
        converter.py
else
    echo "Building Linux executable..."
    python3 -m PyInstaller \
        --name "core-media-converter" \
        --onefile \
        --clean \
        --noconfirm \
        "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}" \
        converter.py
fi

echo ""
echo "✓ Build complete! Output in dist/"
ls -lh dist/
