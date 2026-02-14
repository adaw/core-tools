@echo off
REM CORE SYSTEMS — PDF Tools Build Script (Windows)
cd /d "%~dp0"

echo ◆ CORE SYSTEMS — PDF Tools Builder
echo ====================================

if not exist venv (
    echo → Creating virtual environment...
    python -m venv venv
)

echo → Installing dependencies...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo → Building application...
pyinstaller ^
    --name "PDF Tools" ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --icon=NUL ^
    pdf_tools.py

echo.
echo ✓ Build complete!
echo   Output: dist\PDF Tools.exe
pause
