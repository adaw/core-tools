@echo off
REM CORE Email Transfer & Dedup — Windows Build Script

set APP_NAME=CORE Email Dedup
set ENTRY=email_dedup.py

echo ◆ CORE Email Dedup — Build (Windows)
echo =====================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Install it first.
    exit /b 1
)

REM Install PyInstaller if needed
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "*.spec" del /q *.spec

echo 🔨 Building %APP_NAME%...

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --clean ^
    --noconfirm ^
    %ENTRY%

REM Clean build artifacts
if exist build rmdir /s /q build
if exist "*.spec" del /q *.spec

echo.
echo ✅ Build complete!
echo 📁 Output: dist\%APP_NAME%.exe
echo.
dir dist\
