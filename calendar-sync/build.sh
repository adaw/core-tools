#!/bin/bash
# Build Calendar Sync for macOS
# Requires: pip install pyinstaller

set -e

echo "◆ CORE SYSTEMS — Calendar Sync Builder"
echo "======================================="
echo ""

# Clean previous builds
rm -rf build dist

# Install dependencies if needed
pip install -r requirements.txt 2>/dev/null || true

echo "Building macOS app..."

pyinstaller \
    --name "Calendar Sync" \
    --windowed \
    --onedir \
    --clean \
    --noconfirm \
    --add-data "providers:providers" \
    --add-data "sync:sync" \
    --add-data "ui:ui" \
    --hidden-import icalendar \
    --hidden-import caldav \
    --hidden-import msal \
    --hidden-import google.oauth2 \
    --hidden-import google_auth_oauthlib \
    --hidden-import googleapiclient \
    main.py

echo ""
echo "✅ Build complete!"
echo "   Output: dist/Calendar Sync.app"
echo ""
echo "To create a DMG (optional):"
echo "   hdiutil create -volname 'Calendar Sync' -srcfolder 'dist/Calendar Sync.app' -ov -format UDZO 'dist/CalendarSync.dmg'"
