@echo off
REM CORE Screen Recorder — Windows Build Script
set APP_NAME=CORE Screen Recorder
set SCRIPT=screen_recorder.py

echo === Building %APP_NAME% for Windows ===

pip install -r requirements.txt

pyinstaller ^
    --name "%APP_NAME%" ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data "README.md;." ^
    %SCRIPT%

echo.
echo Build complete: dist\%APP_NAME%.exe
pause
