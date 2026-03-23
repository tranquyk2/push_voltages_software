@echo off
REM Tao shortcut de tu chay khi bat may
setlocal enabledelayedexpansion

REM Lay duong dan thu muc hien tai
set SCRIPT_DIR=%~dp0

REM Lay duong dan Startup folder
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

REM Tao file VBScript launcher de chay exe im lang
set LAUNCHER_VBS=%SCRIPT_DIR%launch_hidden.vbs
(
echo Set oShell = CreateObject("WScript.Shell"^)
echo oShell.Run "%SCRIPT_DIR%Do Tiep Dia.exe", 0, False
) > "%LAUNCHER_VBS%"

REM Tao file VBScript de tao shortcut
set VBS_FILE=%SCRIPT_DIR%make_shortcut.vbs

(
echo Set oWS = WScript.CreateObject("WScript.Shell"^)
echo sLinkFile = "%STARTUP_DIR%\Do Tiep Dia - Arduino Data Logger.lnk"
echo Set oLink = oWS.CreateShortcut(sLinkFile^)
echo oLink.TargetPath = "wscript.exe"
echo oLink.Arguments = "%LAUNCHER_VBS%"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%"
echo oLink.Description = "Do Tiep Dia - Arduino Data Logger"
echo oLink.WindowStyle = 7
echo oLink.Save
echo WScript.Echo "Shortcut created successfully!"
) > "%VBS_FILE%"

REM Chay VBScript
cscript.exe "%VBS_FILE%"

REM Xoa VBScript
del "%VBS_FILE%"

echo.
echo ========================================
echo Setup hoan thanh!
echo Phan mem se tu chay khi bat may.
echo ========================================
pause
