#!/usr/bin/env bash
# CORE Clipboard Manager — macOS / Linux build script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="CORE Clipboard Manager"

echo "⬡ Building ${APP_NAME}…"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Install PyInstaller if missing
if ! python3 -m PyInstaller --version &>/dev/null 2>&1; then
    echo "Installing PyInstaller…"
    pip3 install pyinstaller
fi

# Clean previous build
rm -rf build dist *.spec

# Build
python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    --clean \
    clipboard_manager.py

echo ""
echo "✓ Build complete!"
echo "  Output: dist/${APP_NAME}.app (macOS) or dist/${APP_NAME} (Linux)"
