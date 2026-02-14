#!/bin/bash
# CORE Screen Recorder — macOS Build Script
set -e

APP_NAME="CORE Screen Recorder"
SCRIPT="screen_recorder.py"

echo "=== Building ${APP_NAME} for macOS ==="

# Install deps
pip install -r requirements.txt

# Build .app bundle
pyinstaller \
    --name "${APP_NAME}" \
    --onefile \
    --windowed \
    --noconfirm \
    --clean \
    --add-data "README.md:." \
    "${SCRIPT}"

echo ""
echo "✅ Build complete: dist/${APP_NAME}.app"
echo "   To create DMG: hdiutil create -volname '${APP_NAME}' -srcfolder 'dist/${APP_NAME}.app' -ov -format UDZO '${APP_NAME}.dmg'"
