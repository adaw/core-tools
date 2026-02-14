@echo off
REM CORE Batch Renamer — Windows build script
echo Building CORE Batch Renamer for Windows...

cd /d "%~dp0"

REM Check pyinstaller
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build
pyinstaller ^
    --name "CORE Batch Renamer" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    renamer.py

echo.
echo Build complete: dist\CORE Batch Renamer.exe
pause
