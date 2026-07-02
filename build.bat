@echo off
REM ============================================================
REM  build.bat
REM  Build "Do Tiep Dia" thanh file .exe co logo/icon rieng.
REM  Chay file nay tu THU MUC GOC chua main.py, app.py, config.py,
REM  serial_manager.py, server_client.py, tray_manager.py,
REM  password_dialog.py, autostart.py, va file icon.ico
REM
REM  Yeu cau truoc khi chay:
REM    1. Da cai Python (khuyen nghi dung venv rieng cho build).
REM    2. Da activate venv va cai:
REM         pip install pyinstaller pyserial requests pillow pystray
REM    3. Co san file icon o dang .ico (xem ghi chu ben duoi neu chi
REM       co file .png/.jpg).
REM ============================================================

setlocal

set "APP_NAME=DoTiepDia"
set "ICON_FILE=logo.ico"

echo ============================================================
echo  Building %APP_NAME%.exe
echo ============================================================

REM ---- Kiem tra icon co ton tai khong ----
if not exist "%ICON_FILE%" (
    echo.
    echo [CANH BAO] Khong tim thay %ICON_FILE% trong thu muc hien tai.
    echo App van build duoc nhung se dung icon mac dinh cua Python.
    echo Xem huong dan chuyen doi PNG/JPG sang ICO o cuoi file nay.
    echo.
)

REM ---- Xoa build cu, tranh dinh cache PyInstaller ----
if exist "build" rmdir /s /q "build"
if exist "dist\%APP_NAME%" rmdir /s /q "dist\%APP_NAME%"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

REM ---- Build ----
if exist "%ICON_FILE%" (
    pyinstaller --onedir --windowed --name %APP_NAME% ^
      --icon "%ICON_FILE%" ^
      --collect-all pystray ^
      --collect-all PIL ^
      --hidden-import serial ^
      --hidden-import serial.tools.list_ports ^
      main.py
) else (
    pyinstaller --onedir --windowed --name %APP_NAME% ^
      --collect-all pystray ^
      --collect-all PIL ^
      --hidden-import serial ^
      --hidden-import serial.tools.list_ports ^
      main.py
)

if errorlevel 1 (
    echo.
    echo [LOI] Build that bai. Xem log ben tren de biet nguyen nhan.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  XONG! App nam tai:
echo    dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo  De phan phoi sang may khac: copy nguyen thu muc
echo    dist\%APP_NAME%
echo  (bao gom ca folder _internal ben trong, khong duoc thieu)
echo ============================================================
pause

REM ============================================================
REM  GHI CHU: Neu ban chi co logo dang .png hoac .jpg, can doi
REM  sang .ico truoc. Cach nhanh nhat bang Python (co san Pillow):
REM
REM    python -c "from PIL import Image; Image.open('logo.png').save('logo.ico', sizes=[(16,16),(32,32),(48,48),(256,256)])"
REM
REM  File .ico nen co nhieu size (16x16 den 256x256) de Windows
REM  hien thi dep o moi ngu canh (taskbar, tray, Explorer, shortcut).
REM ============================================================