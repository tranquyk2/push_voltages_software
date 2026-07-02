"""
autostart.py

Đăng ký ứng dụng tự khởi động cùng Windows qua Registry Run key.
Chỉ có tác dụng khi chạy dưới dạng .exe đã đóng gói (PyInstaller);
khi chạy trực tiếp bằng "python app.py" sẽ bỏ qua, không đăng ký gì cả.
"""
import sys

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


def setup_autostart_shortcut(app_name: str = "Do Tiep Dia") -> None:
    if not WINREG_AVAILABLE:
        return
    if not getattr(sys, 'frozen', False):
        return

    try:
        exe_path = sys.executable
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(reg_key)
    except Exception:
        # Thất bại yên tĩnh — không phải lỗi nghiêm trọng, giữ đúng hành vi gốc
        pass