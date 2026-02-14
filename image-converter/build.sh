#!/usr/bin/env bash
# Build CORE Image Converter — macOS .app bundle
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== CORE Image Converter — macOS Build ==="

# Create venv if needed
if [ ! -d ".venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "→ Installing dependencies..."
pip install --upgrade pip -q
pip install Pillow pyinstaller tkinterdnd2 pillow-avif-plugin -q 2>/dev/null || \
pip install Pillow pyinstaller -q

echo "→ Building with PyInstaller..."
pyinstaller \
    --name "CORE Image Converter" \
    --windowed \
    --onefile \
    --clean \
    --noconfirm \
    --add-data "icon.png:." 2>/dev/null || \
pyinstaller \
    --name "CORE Image Converter" \
    --windowed \
    --onefile \
    --clean \
    --noconfirm \
    image_converter.py

echo ""
echo "✓ Build complete!"
echo "  Output: dist/CORE Image Converter.app"
echo ""
