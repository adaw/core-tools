#!/bin/bash
# CORE Batch Renamer — macOS build script
set -e

echo "⬡ Building CORE Batch Renamer for macOS..."

cd "$(dirname "$0")"

# Check pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Clean previous builds
rm -rf build dist

# Build
pyinstaller \
    --name "CORE Batch Renamer" \
    --windowed \
    --onefile \
    --clean \
    --noconfirm \
    renamer.py

echo ""
echo "✓ Build complete: dist/CORE Batch Renamer.app"
echo "  Run: open 'dist/CORE Batch Renamer.app'"
