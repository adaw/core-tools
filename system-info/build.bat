@echo off
cd /d "%~dp0"
echo === CORE SYSTEMS — System Info Builder (Windows) ===

if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

pyinstaller --onefile --windowed ^
    --name "CORE System Info" ^
    system_info.py

echo Build complete: dist\CORE System Info.exe
pause
