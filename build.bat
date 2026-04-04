@echo off
REM Build script for PyInstaller
REM Creates Do Tiep Dia - Arduino Data Logger.exe

cd /d "%~dp0"

echo Building Do Tiep Dia - Arduino Data Logger...
echo.

REM Output directory
set OUTPUT_DIR=c:\Users\quyqu\OneDrive\Máy tính\new_do_tiep_dia

REM Create output directory if not exists
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Remove old build artifacts
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "*.spec" del *.spec

REM Build with PyInstaller
.venv\Scripts\pyinstaller ^
    --onefile ^
    --windowed ^
    --name "Do Tiep Dia - Arduino Data Logger" ^
    --icon=logo.ico ^
    --distpath="%OUTPUT_DIR%" ^
    --workpath="%cd%\build" ^
    arduino_gui.py

echo.
echo Build complete!
echo.
echo Executable location:
echo   "%OUTPUT_DIR%\Do Tiep Dia - Arduino Data Logger.exe"
echo.
pause
