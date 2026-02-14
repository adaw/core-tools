#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== CORE SYSTEMS — System Info Builder (macOS) ==="

# Ensure venv
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q

# Build .app
pyinstaller --onefile --windowed \
    --name "CORE System Info" \
    --add-data "icon.png:." 2>/dev/null || \
pyinstaller --onefile --windowed \
    --name "CORE System Info" \
    system_info.py

echo "✅ Build complete: dist/CORE System Info.app"
