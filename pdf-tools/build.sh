#!/bin/bash
# CORE SYSTEMS — PDF Tools Build Script (macOS/Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "◆ CORE SYSTEMS — PDF Tools Builder"
echo "===================================="

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv venv
fi

echo "→ Installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt

echo "→ Building application..."
pyinstaller \
    --name "PDF Tools" \
    --onefile \
    --windowed \
    --clean \
    --noconfirm \
    pdf_tools.py

echo ""
echo "✓ Build complete!"
echo "  Output: dist/PDF Tools.app (macOS) or dist/PDF Tools (Linux)"
