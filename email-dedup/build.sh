#!/bin/bash
# CORE Email Transfer & Dedup — macOS Build Script
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="CORE Email Dedup"
ENTRY="email_dedup.py"

echo "◆ CORE Email Dedup — Build (macOS)"
echo "==================================="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 not found. Install it first."
    exit 1
fi

# Install PyInstaller if needed
if ! python3 -m PyInstaller --version &>/dev/null 2>&1; then
    echo "📦 Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Clean previous build
rm -rf build dist *.spec

echo "🔨 Building ${APP_NAME}..."

python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name "${APP_NAME}" \
    --clean \
    --noconfirm \
    "$ENTRY"

# Clean build artifacts
rm -rf build *.spec

echo ""
echo "✅ Build complete!"
echo "📁 Output: dist/${APP_NAME}.app"
echo ""
ls -la "dist/"
