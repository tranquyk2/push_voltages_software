import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import json
import requests
from datetime import datetime
from queue import Queue
import sys
import os
import subprocess
import tempfile
from PIL import Image, ImageDraw
import pystray
import winreg

class ArduinoDataLogger:
    # CH340 VID/PID
    CH340_VID = 0x1A86
    CH340_PID = 0x7523
    
    def __init__(self, root):
        self.root = root
        self.root.title("Do Tiep Dia")
        self.root.geometry("400x500")
        self.root.resizable(True, True)
        
        self.ser = None
        self.is_connected = False
        self.data_queue = Queue()
        self.thread = None
        self.running = False
        self.user_disconnected = False
        self.monitor_thread = None
        self.failed_password_attempts = 0
        self.exit_password = "1234"
        self.exit_locked = False
        self.is_minimized = False
        self.tray_thread = None
        
        # Setup auto-start on first run
        self.setup_autostart_shortcut()
        
        # Load settings from file
        self.load_settings()
        
        # Setup UI
        self.setup_ui()
        
        # Auto-detect COM ports
        self.update_com_ports()
        
        # Start auto-reconnect monitor
        self.start_auto_monitor()
        
        # ===== CHỐNG TẮT =====
        # Gán WM_DELETE_WINDOW -> ẩn xuống thay vì tắt
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        # Chặn phím tắt đóng cửa sổ thường gặp - cũng chỉ ẩn xuống
        self.root.bind('<Alt-F4>',        lambda e: self.hide_to_tray())
        self.root.bind('<Control-w>',     lambda e: self.hide_to_tray())
        self.root.bind('<Control-q>',     lambda e: self.hide_to_tray())
        self.root.bind('<Control-F4>',    lambda e: self.hide_to_tray())
        self.root.bind('<F4>',            lambda e: self.hide_to_tray())
        
        # Alt+X -> Tắt ứng dụng nhanh (với xác nhận mật khẩu)
        self.root.bind('<Alt-x>',         lambda e: self.exit_with_password())
        self.root.bind('<Alt-X>',         lambda e: self.exit_with_password())
        # ======================
        
        # Setup System Tray
        self.tray_icon = None
        self.setup_tray_icon()

    def create_tray_icon_image(self):
        """Create a simple icon for the system tray"""
        size = (64, 64)
        image = Image.new('RGB', size, color='white')
        draw = ImageDraw.Draw(image)
        # Draw a simple circle to represent connected/monitoring status
        draw.ellipse([10, 10, 54, 54], fill='blue', outline='navy')
        draw.text((20, 25), "DTD", fill='white')
        return image

    def setup_tray_icon(self):
        """Setup system tray icon with menu"""
        try:
            icon_image = self.create_tray_icon_image()
            menu = (
                pystray.MenuItem("Hiển thị", self.show_from_tray),
                pystray.MenuItem("Ẩn", self.hide_to_tray_from_menu),
                pystray.MenuItem("Tắt ứng dụng", self.on_closing),
            )
            self.tray_icon = pystray.Icon("Do Tiep Dia", icon_image, menu=menu)
        except Exception as e:
            pass  # Tray setup optional

    def hide_to_tray_from_menu(self, icon=None, item=None):
        """Hide to tray from menu (wrapper)"""
        self.hide_to_tray()

    def show_from_tray(self, icon=None, item=None):
        """Show window from tray"""
        self.is_minimized = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus()

    def start_tray_in_thread(self):
        """Start tray icon in a separate thread"""
        if self.tray_icon:
            try:
                self.tray_icon.run()
            except Exception as e:
                pass

    def setup_autostart_shortcut(self):
        """Đăng ký ứng dụng tự động khởi động qua Registry"""
        try:
            # Lấy đường dẫn đến EXE (nếu là PyInstaller thì dùng sys.executable, nếu là EXE thì dùng sys.argv[0])
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                # Nếu chạy từ Python script, thì không đăng ký
                return
            
            # Tên entry trong Registry
            app_name = "Do Tiep Dia"
            
            # Mở Registry key cho Startup
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            # Thêm entry để tự động chạy
            winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(reg_key)
            
        except Exception as e:
            # Yên tĩnh thất bại - không phải lỗi nghiêm trọng
            pass
    
    def setup_ui(self):
        """Setup the user interface"""
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
        
        self.disconnect_btn = ttk.Button(row1, text="Ngắt", command=self.disconnect_arduino, state=tk.DISABLED, width=10)
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
        
        # Row 3: Auto-connect checkbox & Exit button
        row3 = ttk.Frame(control_frame)
        row3.pack(fill=tk.X)
        
        ttk.Checkbutton(
            row3,
            text="Tự động kết nối khi khởi động",
            variable=self.auto_connect_var,
            command=self.save_settings
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
        """Format JSON data for table display"""
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            line_id = json_data.get('line_id', '--')
            self.line_label.config(text=f"Line: {line_id}")
            
            if isinstance(json_data, dict):
                if 'data' in json_data and isinstance(json_data['data'], list):
                    for item_data in json_data['data']:
                        machine_id = item_data.get('machine_id', 'N/A')
                        voltage = item_data.get('voltage', 0)
                        voltage_str = f"{voltage:.1f}" if isinstance(voltage, (int, float)) else str(voltage)
                        self.tree.insert("", "end", values=(f"Machine {machine_id}", voltage_str))
                        
            return True
        except Exception as e:
            return False

    def get_available_ports(self):
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'vid': port.vid,
                'pid': port.pid,
                'is_ch340': port.vid == self.CH340_VID and port.pid == self.CH340_PID
            })
        return ports
    
    def update_com_ports(self):
        ports = self.get_available_ports()
        port_list = [p['device'] for p in ports]
        
        self.com_combo['values'] = port_list
        
        ch340_ports = [p for p in ports if p['is_ch340']]
        if ch340_ports and not self.is_connected:
            self.com_var.set(ch340_ports[0]['device'])
        elif port_list and not self.com_var.get():
            self.com_var.set(port_list[0])
    
    def connect_arduino(self):
        com_port = self.com_var.get()
        
        if not com_port:
            messagebox.showerror("Lỗi", "Vui lòng chọn cổng COM")
            return
        
        try:
            self.ser = serial.Serial(
                port=com_port,
                baudrate=9600,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            
            self.is_connected = True
            self.running = True
            self.user_disconnected = False
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.com_combo.config(state=tk.DISABLED)
            self.server_entry.config(state=tk.DISABLED)
            self.status_label.config(text=f"🟢 Kết nối {com_port}", foreground="green")
            
            self.thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.thread.start()
            
        except serial.SerialException as e:
            self.is_connected = False
            self.running = False
            self.status_label.config(text="⚫ Lỗi kết nối", foreground="red")
    
    def disconnect_arduino(self):
        self.user_disconnected = True
        self.running = False
        if self.ser:
            self.ser.close()
        
        self.is_connected = False
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.com_combo.config(state="readonly")
        self.server_entry.config(state=tk.NORMAL)
        self.status_label.config(text="⚫ Chưa kết nối", foreground="red")
    
    def read_serial_data(self):
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
                                self.root.after(0, lambda d=json_data: self.format_data_display(d))
                                self.send_to_server(json_data)
                            except json.JSONDecodeError:
                                pass
                else:
                    threading.Event().wait(0.1)
                    
            except Exception as e:
                if self.running and not self.user_disconnected:
                    self.is_connected = False
                break
    
    def start_auto_monitor(self):
        self.monitor_thread = threading.Thread(target=self.auto_monitor_arduino, daemon=True)
        self.monitor_thread.start()
    
    def auto_monitor_arduino(self):
        reconnect_delay = 0
        
        while True:
            try:
                if self.user_disconnected:
                    threading.Event().wait(1)
                    continue
                
                if self.is_connected and self.ser and self.ser.is_open:
                    reconnect_delay = 0
                    threading.Event().wait(1)
                    continue
                
                ports = self.get_available_ports()
                ch340_ports = [p for p in ports if p['is_ch340']]
                
                if ch340_ports:
                    best_port = ch340_ports[0]['device']
                    self.root.after(0, lambda p=best_port: self.com_var.set(p))
                    
                    if not self.is_connected:
                        reconnect_delay += 1
                        if reconnect_delay >= 3:
                            self.root.after(0, self.connect_arduino)
                            reconnect_delay = 0
                else:
                    reconnect_delay = 0
                    if self.is_connected:
                        self.is_connected = False
                
                threading.Event().wait(1)
                    
            except Exception as e:
                threading.Event().wait(2)
    
    def send_to_server(self, data):
        server_url = self.server_url_var.get()
        if not server_url or server_url == "http://127.0.0.1:8000/api/voltages":
            return
        
        try:
            requests.post(server_url, json=data, timeout=2)
        except:
            pass
    
    def save_settings(self):
        try:
            settings = {
                'server_url': self.server_url_var.get(),
                'auto_connect': self.auto_connect_var.get(),
                'last_com': self.com_var.get(),
                'exit_password': self.exit_password
            }
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_settings(self):
        self.auto_connect_var = tk.BooleanVar(value=True)
        self.server_url_var = tk.StringVar(value="http://127.0.0.1:8000/api/voltages")
        self.com_var = tk.StringVar()
        
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.server_url_var.set(settings.get('server_url', "http://127.0.0.1:8000/api/voltages"))
                self.auto_connect_var.set(settings.get('auto_connect', True))
                self.com_var.set(settings.get('last_com', ''))
                self.exit_password = settings.get('exit_password', '1234')
        except FileNotFoundError:
            self.save_settings()

    # ================================================================== #
    #  CHỐNG TẮT – Dialog xác nhận mật khẩu                             #
    # ================================================================== #
    def show_password_dialog(self):
        """Hiện hộp thoại nhập mật khẩu. Trả về True nếu đúng."""

        # Nếu đã bị khóa do nhập sai 3 lần
        if self.exit_locked:
            messagebox.showerror(
                "Đã bị khóa",
                "Chức năng tắt ứng dụng đã bị khóa.\n"
                "Dùng Task Manager (Ctrl+Shift+Esc) để tắt."
            )
            return False

        # Tạo dialog con
        dialog = tk.Toplevel(self.root)
        dialog.title("Xác nhận tắt ứng dụng")
        dialog.geometry("320x160")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()                   # chặn tương tác cửa sổ chính
        dialog.focus_force()

        # Ngăn chính dialog bị đóng bằng nút X của nó
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        ttk.Label(dialog, text="Nhập mật khẩu để tắt ứng dụng:",
                  font=("Arial", 10)).pack(pady=12)

        password_var = tk.StringVar()
        pw_entry = ttk.Entry(dialog, textvariable=password_var,
                             show="*", width=28, font=("Arial", 10))
        pw_entry.pack(pady=4)
        pw_entry.focus()

        # Dùng list để truyền kết quả ra ngoài closure
        result = [False]

        def check_password():
            if password_var.get() == self.exit_password:
                result[0] = True
                self.failed_password_attempts = 0
                dialog.destroy()
            else:
                self.failed_password_attempts += 1
                remaining = 3 - self.failed_password_attempts

                if remaining <= 0:
                    self.exit_locked = True
                    dialog.destroy()
                    messagebox.showerror(
                        "Đã bị khóa",
                        "Sai mật khẩu 3 lần!\n"
                        "Chức năng tắt ứng dụng đã bị khóa.\n"
                        "Dùng Task Manager (Ctrl+Shift+Esc) để tắt."
                    )
                    return

                messagebox.showerror(
                    "Sai mật khẩu",
                    f"Mật khẩu không đúng! Còn {remaining} lần thử."
                )
                password_var.set("")
                pw_entry.focus()

        pw_entry.bind('<Return>', lambda e: check_password())
        ttk.Button(dialog, text="  Xác nhận  ", command=check_password).pack(pady=10)

        # Chặn Alt-F4 trong dialog
        dialog.bind('<Alt-F4>', lambda e: "break")

        # Chờ dialog đóng (blocking)
        self.root.wait_window(dialog)
        return result[0]

    def exit_with_password(self):
        """Alt+X hotkey - Tắt ứng dụng nhanh với xác nhận mật khẩu"""
        if self.exit_locked:
            messagebox.showerror(
                "Bị khóa",
                "Chức năng tắt đã bị khóa vì sai mật khẩu 3 lần!\n"
                "Dùng Task Manager (Ctrl+Shift+Esc) để tắt."
            )
            return
        
        # Show password dialog
        if not self.show_password_dialog():
            return
        
        # Password correct - close app
        self._do_close()

    def _do_close(self):
        """Thực hiện đóng ứng dụng (không kiểm tra mật khẩu)"""
        self.user_disconnected = True
        self.running = False
        if self.is_connected and self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.save_settings()
        self.root.quit()
        self.root.destroy()

    def on_closing(self):
        """Xử lý sự kiện tắt ứng dụng – yêu cầu mật khẩu."""
        if not self.show_password_dialog():
            # Sai mật khẩu hoặc bị khóa -> không tắt
            return
        
        # Mật khẩu đúng -> dọn dẹp và thoát
        self._do_close()

    def hide_to_tray(self, event=None):
        """Chặn đóng window - nút X không hoạt động"""
        # Chặn event đóng cửa sổ, bạn không thể tắt ứng dụng này bằng nút X
        # Nếu muốn tắt: mở Task Manager → tìm "Do Tiep Dia" → End Task
        return "break"  # Chặn hoàn toàn event mặc định


def main():
    root = tk.Tk()
    app = ArduinoDataLogger(root)
    root.mainloop()

if __name__ == "__main__":
    main()
