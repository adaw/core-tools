#!/bin/bash
# CORE Duplicate Finder — macOS build script
set -e

echo "⬡ Building CORE Duplicate Finder for macOS..."

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
    --name "CORE Duplicate Finder" \
    --windowed \
    --onefile \
    --clean \
    --noconfirm \
    finder.py

echo ""
echo "✓ Build complete: dist/CORE Duplicate Finder.app"
echo "  Run: open 'dist/CORE Duplicate Finder.app'"
