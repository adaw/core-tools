@echo off
REM CORE Duplicate Finder — Windows build script
echo [*] Building CORE Duplicate Finder for Windows...

cd /d "%~dp0"

REM Check pyinstaller
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build
pyinstaller ^
    --name "CORE Duplicate Finder" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    finder.py

echo.
echo [OK] Build complete: dist\CORE Duplicate Finder.exe
pause
