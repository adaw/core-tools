@echo off
REM CORE Clipboard Manager — Windows build script

set APP_NAME=CORE Clipboard Manager

echo ⬡ Building %APP_NAME%...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: python not found
    exit /b 1
)

REM Install PyInstaller if missing
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
del /q *.spec 2>nul

REM Build
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --clean ^
    clipboard_manager.py

echo.
echo ✓ Build complete!
echo   Output: dist\%APP_NAME%.exe
