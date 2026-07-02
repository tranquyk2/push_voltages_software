"""
tray_manager.py

Quản lý icon System Tray: menu Hiện/Ẩn/Tắt ứng dụng.

LƯU Ý: ở bản gốc, hàm start_tray_in_thread() được định nghĩa nhưng KHÔNG
BAO GIỜ được gọi ở đâu cả — nghĩa là icon tray tạo ra nhưng .run() không
chạy, nên icon thực tế không hề hiện lên khay hệ thống. Ở bản tách file
này mình đã gọi self.tray.start() trong app.py để icon thật sự hoạt động;
nếu bạn muốn giữ nguyên hành vi cũ (tray không hiện), chỉ cần không gọi
tray.start() trong app.py.
"""
import threading

from PIL import Image, ImageDraw

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


class TrayManager:
    def __init__(self, app_name: str, on_show, on_hide, on_exit):
        self.app_name = app_name
        self._on_show = on_show
        self._on_hide = on_hide
        self._on_exit = on_exit
        self.icon = None
        self._thread = None

        if PYSTRAY_AVAILABLE:
            self._build_icon()

    def _create_icon_image(self):
        size = (64, 64)
        image = Image.new('RGB', size, color='white')
        draw = ImageDraw.Draw(image)
        draw.ellipse([10, 10, 54, 54], fill='blue', outline='navy')
        draw.text((20, 25), "DTD", fill='white')
        return image

    def _build_icon(self):
        try:
            icon_image = self._create_icon_image()
            menu = (
                pystray.MenuItem("Hiển thị", lambda icon=None, item=None: self._on_show()),
                pystray.MenuItem("Ẩn", lambda icon=None, item=None: self._on_hide()),
                pystray.MenuItem("Tắt ứng dụng", lambda icon=None, item=None: self._on_exit()),
            )
            self.icon = pystray.Icon(self.app_name, icon_image, menu=menu)
        except Exception:
            self.icon = None

    def start(self):
        """Chạy icon tray trong thread riêng, không block UI chính."""
        if not self.icon:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.icon.run()
        except Exception:
            pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass