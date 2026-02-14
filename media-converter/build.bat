@echo off
REM CORE Media Converter — Windows Build Script

echo ◆ CORE Media Converter — Build
echo ================================

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: python not found. Please install Python 3.10+.
    exit /b 1
)

REM Install PyInstaller if needed
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Build args
set EXTRA_ARGS=
if exist "ffmpeg.exe" (
    echo Found local ffmpeg.exe — bundling.
    set EXTRA_ARGS=%EXTRA_ARGS% --add-binary "ffmpeg.exe;."
)
if exist "ffprobe.exe" (
    echo Found local ffprobe.exe — bundling.
    set EXTRA_ARGS=%EXTRA_ARGS% --add-binary "ffprobe.exe;."
)

echo Building Windows .exe...
python -m PyInstaller ^
    --name "CORE Media Converter" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    %EXTRA_ARGS% ^
    converter.py

echo.
echo Done! Output in dist\
dir dist\
pause
