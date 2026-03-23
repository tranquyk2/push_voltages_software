@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ===== Auto-Start Setup =====
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_DIR%\Do Tiep Dia.lnk
set EXE_PATH=%cd%\Do Tiep Dia.exe

if not exist "%SHORTCUT_PATH%" (
    set VBS_FILE=%TEMP%\setup_%RANDOM%.vbs
    (
        echo Set oWS = WScript.CreateObject("WScript.Shell"^)
        echo Set oLink = oWS.CreateShortcut("%SHORTCUT_PATH%"^)
        echo oLink.TargetPath = "%EXE_PATH%"
        echo oLink.WorkingDirectory = "%cd%"
        echo oLink.WindowStyle = 1
        echo oLink.Save
    ) > "!VBS_FILE!"
    cscript.exe /nologo "!VBS_FILE!" >nul 2>&1
    del "!VBS_FILE!" >nul 2>&1
)

REM ===== Run Exe =====
if exist "%EXE_PATH%" (
    "%EXE_PATH%"
) else (
    echo Error: Exe file not found!
    pause
)
