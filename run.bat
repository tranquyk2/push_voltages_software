@echo off
REM Auto-setup auto-start on first run
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Check if shortcut exists in Startup folder
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_DIR%\Do Tiep Dia - Arduino Data Logger.lnk

REM Create shortcut if it doesn't exist
if not exist "%SHORTCUT_PATH%" (
    echo Setting up auto-start...
    
    REM Create VBScript to make shortcut
    set VBS_FILE=%TEMP%\make_shortcut_%RANDOM%.vbs
    (
        echo Set oWS = WScript.CreateObject("WScript.Shell"^)
        echo sLinkFile = "%SHORTCUT_PATH%"
        echo Set oLink = oWS.CreateShortcut(sLinkFile^)
        echo oLink.TargetPath = "%cd%\run.bat"
        echo oLink.WorkingDirectory = "%cd%"
        echo oLink.Description = "Do Tiep Dia - Arduino Data Logger"
        echo oLink.WindowStyle = 1
        echo oLink.Save
    ) > "!VBS_FILE!"
    
    REM Run VBScript
    cscript.exe /nologo "!VBS_FILE!" >nul 2>&1
    del "!VBS_FILE!" >nul 2>&1
    
    echo Auto-start setup completed!
    timeout /t 2 /nobreak >nul
)

REM Run the application
.venv\Scripts\python.exe arduino_gui.py
