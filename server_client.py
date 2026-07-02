"""
server_client.py

Gửi dữ liệu đọc được từ Arduino lên server qua HTTP POST.
"""
from typing import Any, Dict

import requests

# URL mặc định — cố tình KHÔNG gửi dữ liệu nếu người dùng chưa đổi URL này,
# tránh gửi nhầm lên server đặt sẵn khi chưa cấu hình thật.
DEFAULT_SERVER_URL = "http://192.168.100.168:84/api/voltages"


def send_to_server(server_url: str, data: Dict[str, Any], timeout: float = 2.0) -> None:
    if not server_url or server_url == DEFAULT_SERVER_URL:
        return
    try:
        requests.post(server_url, json=data, timeout=timeout)
    except Exception:
        # Lỗi mạng không được làm gián đoạn việc đọc serial
        pass