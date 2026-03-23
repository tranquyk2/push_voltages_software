@echo off
REM Do Tiep Dia - Arduino Data Logger
REM Wrapper script that runs exe and sets up auto-start

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Check if exe exists in dist folder
if not exist "dist\Do Tiep Dia - Arduino Data Logger.exe" (
    echo Error: Executable not found!
    echo Please run "build.bat" first to create the executable.
    pause
    exit /b 1
)

REM Auto-start setup on first run
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_DIR%\Do Tiep Dia - Arduino Data Logger.lnk
set EXE_PATH=%cd%\dist\Do Tiep Dia - Arduino Data Logger.exe

REM Create shortcut if it doesn't exist
if not exist "%SHORTCUT_PATH%" (
    echo Setting up auto-start...
    
    REM Create VBScript to make shortcut
    set VBS_FILE=%TEMP%\make_shortcut_%RANDOM%.vbs
    (
        echo Set oWS = WScript.CreateObject("WScript.Shell"^)
        echo sLinkFile = "%SHORTCUT_PATH%"
        echo Set oLink = oWS.CreateShortcut(sLinkFile^)
        echo oLink.TargetPath = "%EXE_PATH%"
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

REM Run the executable
"%EXE_PATH%"
