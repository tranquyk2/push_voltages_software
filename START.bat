@echo off
REM Do Tiep Dia - Arduino Data Logger
REM One-click launcher with auto-setup
REM Just double-click this file to run!

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Check if exe exists
if not exist "dist\Do Tiep Dia - Arduino Data Logger.exe" (
    echo.
    echo Error: Executable not found in dist\ folder
    echo.
    echo Please run "build.bat" first to create the executable:
    echo   build.bat
    echo.
    pause
    exit /b 1
)

REM Auto-start setup
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_DIR%\Do Tiep Dia - Arduino Data Logger.lnk
set EXE_PATH=%cd%\dist\Do Tiep Dia - Arduino Data Logger.exe

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

REM Run exe
"%EXE_PATH%"
