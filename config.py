"""
config.py

Đọc/ghi file config.json cạnh file .exe (hoặc cạnh script khi chạy bằng
python). Tách riêng để UI và logic khác không cần biết chi tiết đường dẫn
file nằm ở đâu.
"""
import json
import os
import sys

DEFAULT_SETTINGS = {
    'server_url': "http://192.168.100.168:84/api/voltages",
    'auto_connect': True,
    'last_com': '',
    'exit_password': '1234',
}


def get_config_path() -> str:
    """Trả về đường dẫn config.json — luôn nằm cạnh file .exe khi đã đóng
    gói bằng PyInstaller, hoặc cạnh file .py khi chạy trực tiếp."""
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, 'config.json')


def load_settings() -> dict:
    """Đọc settings từ config.json. Nếu file chưa tồn tại, tạo mới với giá
    trị mặc định. Nếu key nào thiếu trong file cũ, tự bổ sung từ default."""
    path = get_config_path()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        merged = DEFAULT_SETTINGS.copy()
        merged.update(settings)
        return merged
    except FileNotFoundError:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    """Ghi settings xuống config.json. Lỗi ghi file bị nuốt im lặng (không
    làm crash app) — giữ đúng hành vi bản gốc."""
    path = get_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass