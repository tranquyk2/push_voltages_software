"""
app.py

Lớp ứng dụng chính: xây UI, và nối các module (config, serial_manager,
server_client, tray_manager, autostart, password_dialog) lại với nhau.
Không chứa logic chi tiết của từng phần — chỉ điều phối.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from config import load_settings, save_settings as save_settings_to_file
from serial_manager import SerialManager
from server_client import send_to_server, DEFAULT_SERVER_URL
from autostart import setup_autostart_shortcut
from tray_manager import TrayManager
from password_dialog import PasswordGate


class DoTiepDiaApp:
    APP_NAME = "Do Tiep Dia"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(self.APP_NAME)
        self.root.geometry("400x500")
        self.root.resizable(True, True)

        # Đăng ký tự khởi động cùng Windows (chỉ có tác dụng khi chạy .exe)
        setup_autostart_shortcut(self.APP_NAME)

        # ── Load cấu hình đã lưu ─────────────────────────────────────────
        settings = load_settings()
        self.server_url_var = tk.StringVar(value=settings.get('server_url', DEFAULT_SERVER_URL))
        self.auto_connect_var = tk.BooleanVar(value=settings.get('auto_connect', True))
        self.com_var = tk.StringVar(value=settings.get('last_com', ''))
        self.exit_password = settings.get('exit_password', '1234')

        # ── Serial manager: toàn bộ logic giao tiếp Arduino ──────────────
        self.serial_mgr = SerialManager(
            on_data=self._on_serial_data,
            on_status_change=self._on_serial_status_change,
        )

        # ── Bảo vệ mật khẩu trước khi thoát ──────────────────────────────
        self.password_gate = PasswordGate(get_password=lambda: self.exit_password)

        self._build_ui()
        self.update_com_ports()

        # Bật lại tự động dò/kết nối liên tục — gắn với checkbox
        # "Tự động kết nối khi khởi động": khi tắt, monitor vẫn cập nhật
        # danh sách cổng COM nhưng KHÔNG tự ý mở kết nối.
        self.serial_mgr.start_auto_monitor(
            get_selected_port=self.com_var.get,
            set_selected_port=lambda p: self.root.after(0, self.com_var.set, p),
            should_auto_connect=self.auto_connect_var.get,
        )

        # ===== CHỐNG TẮT =====
        # Gán WM_DELETE_WINDOW -> ẩn xuống thay vì tắt
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Chặn phím tắt đóng cửa sổ thường gặp - cũng chỉ ẩn xuống
        self.root.bind('<Alt-F4>',     lambda e: self.hide_to_tray())
        self.root.bind('<Control-w>',  lambda e: self.hide_to_tray())
        self.root.bind('<Control-q>',  lambda e: self.hide_to_tray())
        self.root.bind('<Control-F4>', lambda e: self.hide_to_tray())
        self.root.bind('<F4>',         lambda e: self.hide_to_tray())

        # Alt+X -> Tắt ứng dụng nhanh (với xác nhận mật khẩu)
        self.root.bind('<Alt-x>', lambda e: self.exit_with_password())
        self.root.bind('<Alt-X>', lambda e: self.exit_with_password())
        # ======================

        # ── System Tray ───────────────────────────────────────────────
        self.tray = TrayManager(
            app_name=self.APP_NAME,
            on_show=self.show_from_tray,
            on_hide=self.hide_to_tray,
            on_exit=self.on_closing,
        )
        self.tray.start()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        control_frame = ttk.Frame(self.root)
        control_frame.pack(padx=8, pady=8, fill=tk.X)

        # Row 1: COM port & buttons
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(row1, text="COM:").pack(side=tk.LEFT, padx=(0, 3))
        self.com_combo = ttk.Combobox(row1, textvariable=self.com_var, width=10, state="readonly")
        self.com_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.com_combo.bind('<<ComboboxSelected>>', lambda e: self.update_com_ports())

        self.connect_btn = ttk.Button(row1, text="Kết nối", command=self.connect_arduino, width=10)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 3))

        self.disconnect_btn = ttk.Button(row1, text="Ngắt", command=self.disconnect_arduino,
                                          state=tk.DISABLED, width=10)
        self.disconnect_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.status_label = ttk.Label(row1, text="⚫ Chưa kết nối", font=("Arial", 8, "bold"), foreground="red")
        self.status_label.pack(side=tk.RIGHT)

        # Row 2: Server URL
        row2 = ttk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(row2, text="Server:", font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 3))
        self.server_entry = ttk.Entry(row2, textvariable=self.server_url_var, width=30, font=("Arial", 7))
        self.server_entry.pack(side=tk.LEFT, padx=(0, 3), fill=tk.X, expand=True)

        ttk.Button(row2, text="Lưu", command=self.save_settings, width=4).pack(side=tk.LEFT)

        # Row 3: Auto-connect checkbox
        row3 = ttk.Frame(control_frame)
        row3.pack(fill=tk.X)

        ttk.Checkbutton(
            row3,
            text="Tự động kết nối khi khởi động",
            variable=self.auto_connect_var,
            command=self.save_settings,
        ).pack(side=tk.LEFT)

        # Data display area
        display_frame = ttk.Frame(self.root)
        display_frame.pack(padx=8, pady=(5, 8), fill=tk.BOTH, expand=True)

        info_frame = ttk.Frame(display_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        self.line_label = ttk.Label(info_frame, text="Line: --", font=("Arial", 10, "bold"), foreground="blue")
        self.line_label.pack(side=tk.LEFT, padx=5)

        table_frame = ttk.LabelFrame(display_frame, text="Dữ liệu Thiết Bị", padding=5)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Thiết Bị", "Giá Trị")
        self.tree = ttk.Treeview(table_frame, columns=columns, height=20, show="headings")
        self.tree.column("Thiết Bị", width=150, anchor="center")
        self.tree.column("Giá Trị", width=120, anchor="center")
        self.tree.heading("Thiết Bị", text="Thiết Bị")
        self.tree.heading("Giá Trị", text="Giá Trị (V)")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def format_data_display(self, json_data):
        """Format JSON data cho bảng hiển thị."""
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)

            line_id = json_data.get('line_id', '--')
            self.line_label.config(text=f"Line: {line_id}")

            if isinstance(json_data, dict) and isinstance(json_data.get('data'), list):
                for item_data in json_data['data']:
                    machine_id = item_data.get('machine_id', 'N/A')
                    voltage = item_data.get('voltage', 0)
                    voltage_str = f"{voltage:.1f}" if isinstance(voltage, (int, float)) else str(voltage)
                    self.tree.insert("", "end", values=(f"Machine {machine_id}", voltage_str))

            return True
        except Exception:
            return False

    # ── COM ports ─────────────────────────────────────────────────────────
    def update_com_ports(self):
        ports = self.serial_mgr.get_available_ports()
        port_list = [p['device'] for p in ports]
        self.com_combo['values'] = port_list

        ch340_ports = [p for p in ports if p['is_ch340']]
        if ch340_ports and not self.serial_mgr.is_connected:
            self.com_var.set(ch340_ports[0]['device'])
        elif port_list and not self.com_var.get():
            self.com_var.set(port_list[0])

    # ── Connect / disconnect ─────────────────────────────────────────────
    def connect_arduino(self):
        com_port = self.com_var.get()
        if not com_port:
            messagebox.showerror("Lỗi", "Vui lòng chọn cổng COM")
            return
        self.serial_mgr.connect(com_port)

    def disconnect_arduino(self):
        self.serial_mgr.disconnect()

    def _on_serial_status_change(self, text: str, connected: bool):
        """Callback từ SerialManager — có thể được gọi từ thread nền,
        nên luôn marshal việc update widget qua root.after()."""
        def _update():
            if connected:
                self.status_label.config(text=f"🟢 {text}", foreground="green")
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.NORMAL)
                self.com_combo.config(state=tk.DISABLED)
                self.server_entry.config(state=tk.DISABLED)
            else:
                self.status_label.config(text=f"⚫ {text}", foreground="red")
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.DISABLED)
                self.com_combo.config(state="readonly")
                self.server_entry.config(state=tk.NORMAL)
        self.root.after(0, _update)

    def _on_serial_data(self, json_data: dict):
        """Callback từ SerialManager — chạy trên thread đọc serial."""
        self.root.after(0, self.format_data_display, json_data)
        send_to_server(self.server_url_var.get(), json_data)

    # ── Settings ─────────────────────────────────────────────────────────
    def save_settings(self):
        settings = {
            'server_url': self.server_url_var.get(),
            'auto_connect': self.auto_connect_var.get(),
            'last_com': self.com_var.get(),
            'exit_password': self.exit_password,
        }
        save_settings_to_file(settings)

    # ── Exit / tray (chống tắt) ──────────────────────────────────────────
    def exit_with_password(self):
        """Alt+X hotkey - tắt ứng dụng nhanh với xác nhận mật khẩu."""
        if self.password_gate.locked:
            messagebox.showerror(
                "Bị khóa",
                "Chức năng tắt đã bị khóa vì sai mật khẩu 3 lần!\n"
                "Dùng Task Manager (Ctrl+Shift+Esc) để tắt."
            )
            return
        if not self.password_gate.prompt(self.root):
            return
        self._do_close()

    def on_closing(self):
        """Xử lý sự kiện tắt ứng dụng (menu tray "Tắt ứng dụng") — yêu cầu mật khẩu."""
        if not self.password_gate.prompt(self.root):
            return
        self._do_close()

    def _do_close(self):
        """Thực hiện đóng ứng dụng (không kiểm tra mật khẩu)."""
        self.serial_mgr.user_disconnected = True
        self.serial_mgr.running = False
        if self.serial_mgr.is_connected and self.serial_mgr.ser:
            try:
                self.serial_mgr.ser.close()
            except Exception:
                pass
        self.save_settings()
        self.tray.stop()
        self.root.quit()
        self.root.destroy()

    def hide_to_tray(self, event=None):
        """Chặn đóng window - nút X không hoạt động, chỉ ẩn xuống tray."""
        return "break"

    def show_from_tray(self, icon=None, item=None):
        self.root.deiconify()
        self.root.lift()
        self.root.focus()