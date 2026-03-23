@echo off
cd /d "%~dp0"
if exist "Do Tiep Dia.exe" (
    "Do Tiep Dia.exe"
) else (
    echo Error: Do Tiep Dia.exe not found
    pause
)
