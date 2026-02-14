@echo off
REM Build Calendar Sync for Windows
REM Requires: pip install pyinstaller

echo ◆ CORE SYSTEMS — Calendar Sync Builder
echo =======================================
echo.

REM Clean previous builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM Install dependencies
pip install -r requirements.txt 2>nul

echo Building Windows executable...

pyinstaller ^
    --name "CalendarSync" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    --add-data "providers;providers" ^
    --add-data "sync;sync" ^
    --add-data "ui;ui" ^
    --hidden-import icalendar ^
    --hidden-import caldav ^
    --hidden-import msal ^
    --hidden-import google.oauth2 ^
    --hidden-import google_auth_oauthlib ^
    --hidden-import googleapiclient ^
    main.py

echo.
echo ✅ Build complete!
echo    Output: dist\CalendarSync.exe
