"""
serial_manager.py

Toàn bộ logic giao tiếp Serial với Arduino: dò cổng CH340, kết nối/ngắt,
đọc dữ liệu JSON theo dòng, và tự động dò/kết nối lại liên tục khi mất
kết nối (có thể bật/tắt qua checkbox "Tự động kết nối khi khởi động").

Không đụng tới bất kỳ widget Tkinter nào trực tiếp — mọi cập nhật UI đều
đi qua callback (on_data / on_status_change) để lớp gọi (app.py) tự quyết
định cách hiển thị và tự lo việc marshal sang main thread bằng root.after().
"""
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import serial
import serial.tools.list_ports


class SerialManager:
    # CH340 VID/PID — chip USB-to-Serial phổ biến trên board Arduino clone
    CH340_VID = 0x1A86
    CH340_PID = 0x7523

    def __init__(
        self,
        on_data: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status_change: Optional[Callable[[str, bool], None]] = None,
    ):
        """
        on_data(json_data): gọi mỗi khi đọc được 1 dòng JSON hợp lệ.
        on_status_change(text, connected): gọi mỗi khi trạng thái kết nối
            thay đổi (đã kết nối / ngắt / lỗi).
        """
        self.ser: Optional[serial.Serial] = None
        self.is_connected = False
        self.running = False
        self.user_disconnected = False

        self._on_data = on_data
        self._on_status_change = on_status_change

        self._read_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None

    # ── Port discovery ───────────────────────────────────────────────────
    def get_available_ports(self) -> List[Dict[str, Any]]:
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'vid': port.vid,
                'pid': port.pid,
                'is_ch340': port.vid == self.CH340_VID and port.pid == self.CH340_PID,
            })
        return ports

    def find_ch340_port(self) -> Optional[str]:
        ch340_ports = [p for p in self.get_available_ports() if p['is_ch340']]
        return ch340_ports[0]['device'] if ch340_ports else None

    # ── Connect / disconnect ─────────────────────────────────────────────
    def connect(self, com_port: str) -> bool:
        """Mở cổng serial và bắt đầu thread đọc dữ liệu.
        An toàn khi gọi từ bất kỳ thread nào (không đụng Tkinter trực tiếp)."""
        if not com_port:
            return False
        try:
            self.ser = serial.Serial(
                port=com_port,
                baudrate=9600,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
            )
            self.is_connected = True
            self.running = True
            self.user_disconnected = False
            self._notify_status(f"Kết nối {com_port}", True)

            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except serial.SerialException:
            self.is_connected = False
            self.running = False
            self._notify_status("Lỗi kết nối", False)
            return False

    def disconnect(self):
        """Người dùng chủ động ngắt kết nối — auto-monitor sẽ KHÔNG tự
        connect lại cho tới khi connect() được gọi lại thủ công (hoặc
        user_disconnected được reset về False, xem app.py)."""
        self.user_disconnected = True
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.is_connected = False
        self._notify_status("Chưa kết nối", False)

    def _notify_status(self, text: str, connected: bool):
        if self._on_status_change:
            self._on_status_change(text, connected)

    # ── Reading loop ─────────────────────────────────────────────────────
    def _read_loop(self):
        buffer = ""
        while self.running and self.ser:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            try:
                                json_data = json.loads(line)
                                if self._on_data:
                                    self._on_data(json_data)
                            except json.JSONDecodeError:
                                pass
                else:
                    time.sleep(0.1)
            except Exception:
                if self.running and not self.user_disconnected:
                    self.is_connected = False
                break

    # ── Auto-reconnect monitor ──────────────────────────────────────────
    def start_auto_monitor(
        self,
        get_selected_port: Callable[[], str],
        set_selected_port: Callable[[str], None],
        should_auto_connect: Optional[Callable[[], bool]] = None,
    ):
        """Chạy thread nền liên tục: dò cổng CH340, tự set vào UI, và tự
        connect lại sau 3 giây liên tục thấy board cắm vào mà chưa kết nối.

        should_auto_connect: hàm trả về True/False, được kiểm tra MỖI LẦN
        trước khi tự động gọi connect(). Gắn với checkbox "Tự động kết nối
        khi khởi động" — khi tắt, monitor vẫn cập nhật danh sách cổng COM
        nhưng KHÔNG tự ý mở kết nối; người dùng phải bấm "Kết nối" thủ công.
        Nếu không truyền, mặc định luôn cho phép tự kết nối."""
        self._monitor_thread = threading.Thread(
            target=self._auto_monitor_loop,
            args=(get_selected_port, set_selected_port, should_auto_connect),
            daemon=True,
        )
        self._monitor_thread.start()

    def _auto_monitor_loop(self, get_selected_port, set_selected_port, should_auto_connect):
        reconnect_delay = 0
        while True:
            try:
                if self.user_disconnected:
                    time.sleep(1)
                    continue

                if self.is_connected and self.ser and self.ser.is_open:
                    reconnect_delay = 0
                    time.sleep(1)
                    continue

                best_port = self.find_ch340_port()
                if best_port:
                    set_selected_port(best_port)
                    allowed = should_auto_connect() if should_auto_connect else True
                    if not self.is_connected and allowed:
                        reconnect_delay += 1
                        if reconnect_delay >= 3:
                            self.connect(best_port)
                            reconnect_delay = 0
                    else:
                        reconnect_delay = 0
                else:
                    reconnect_delay = 0
                    if self.is_connected:
                        self.is_connected = False

                time.sleep(1)
            except Exception:
                time.sleep(2)