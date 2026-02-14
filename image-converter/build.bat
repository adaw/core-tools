@echo off
REM Build CORE Image Converter — Windows .exe
echo === CORE Image Converter — Windows Build ===

cd /d "%~dp0"

if not exist ".venv" (
    echo → Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo → Installing dependencies...
pip install --upgrade pip -q
pip install Pillow pyinstaller tkinterdnd2 pillow-avif-plugin -q 2>nul || pip install Pillow pyinstaller -q

echo → Building with PyInstaller...
pyinstaller ^
    --name "CORE Image Converter" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    --icon=icon.ico ^
    image_converter.py 2>nul || ^
pyinstaller ^
    --name "CORE Image Converter" ^
    --windowed ^
    --onefile ^
    --clean ^
    --noconfirm ^
    image_converter.py

echo.
echo Done! Output: dist\CORE Image Converter.exe
pause
