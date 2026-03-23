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

class ArduinoDataLogger:
    # CH340 VID/PID
    CH340_VID = 0x1A86
    CH340_PID = 0x7523
    
    def __init__(self, root):
        self.root = root
        self.root.title("Do Tiep Dia - Arduino Data Logger")
        self.root.geometry("400x500")
        self.root.resizable(True, True)
        
        self.ser = None
        self.is_connected = False
        self.data_queue = Queue()
        self.thread = None
        self.running = False
        self.user_disconnected = False
        self.monitor_thread = None
        
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
        
        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_autostart_shortcut(self):
        """Create Windows Startup shortcut on first run"""
        try:
            startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
            shortcut_path = os.path.join(startup_dir, "Do Tiep Dia.lnk")
            
            # Only create if doesn't exist
            if not os.path.exists(shortcut_path):
                exe_path = sys.executable  # Path to running exe
                
                # Create VBScript to generate shortcut
                vbs_content = f"""Set oWS = WScript.CreateObject("WScript.Shell")
Set oLink = oWS.CreateShortcut("{shortcut_path}")
oLink.TargetPath = "{exe_path}"
oLink.WorkingDirectory = "{os.path.dirname(exe_path)}"
oLink.WindowStyle = 1
oLink.Save
"""
                
                # Write and run VBScript
                vbs_file = os.path.join(tempfile.gettempdir(), f"setup_{os.getpid()}.vbs")
                with open(vbs_file, 'w', encoding='utf-8') as f:
                    f.write(vbs_content)
                
                subprocess.run(['cscript.exe', '/nologo', vbs_file], capture_output=True)
                
                # Clean up
                try:
                    os.remove(vbs_file)
                except:
                    pass
        except:
            pass  # Silently fail if auto-start setup fails
    
    def setup_ui(self):
        """Setup the user interface"""
        # Top control frame - more compact
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
        
        # Status label on the right
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
            command=self.save_settings
        ).pack(side=tk.LEFT)
        
        # Data display area
        display_frame = ttk.Frame(self.root)
        display_frame.pack(padx=8, pady=(5, 8), fill=tk.BOTH, expand=True)
        
        # Top info bar with line number
        info_frame = ttk.Frame(display_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.line_label = ttk.Label(info_frame, text="Line: --", font=("Arial", 10, "bold"), foreground="blue")
        self.line_label.pack(side=tk.LEFT, padx=5)
        
        # Table for data (full width)
        table_frame = ttk.LabelFrame(display_frame, text="Dữ liệu Thiết Bị", padding=5)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for data display
        columns = ("Thiết Bị", "Giá Trị")
        self.tree = ttk.Treeview(table_frame, columns=columns, height=20, show="headings")
        self.tree.column("Thiết Bị", width=150, anchor="center")
        self.tree.column("Giá Trị", width=120, anchor="center")
        self.tree.heading("Thiết Bị", text="Thiết Bị")
        self.tree.heading("Giá Trị", text="Giá Trị (V)")
        
        # Scrollbar for tree
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Start polling for queue messages
        # Removed: no longer needed
        pass
    
    def format_data_display(self, json_data):
        """Format JSON data for table display"""
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Extract line_id if available
            line_id = json_data.get('line_id', '--')
            self.line_label.config(text=f"Line: {line_id}")
            
            # Extract data
            if isinstance(json_data, dict):
                if 'data' in json_data and isinstance(json_data['data'], list):
                    # Format: [{"machine_id": 1, "voltage": 206.5}, ...]
                    for item_data in json_data['data']:
                        machine_id = item_data.get('machine_id', 'N/A')
                        voltage = item_data.get('voltage', 0)
                        
                        # Format voltage with 1 decimal place
                        voltage_str = f"{voltage:.1f}" if isinstance(voltage, (int, float)) else str(voltage)
                        
                        self.tree.insert("", "end", values=(f"Machine {machine_id}", voltage_str))
                        
            return True
        except Exception as e:
            return False

    
    def get_available_ports(self):
        """Get list of available COM ports with CH340"""
        ports = []
        all_ports = serial.tools.list_ports.comports()
        
        for port in all_ports:
            ports.append({
                'device': port.device,
                'description': port.description,
                'vid': port.vid,
                'pid': port.pid,
                'is_ch340': port.vid == self.CH340_VID and port.pid == self.CH340_PID
            })
        
        return ports
    
    def update_com_ports(self):
        """Update COM port list"""
        ports = self.get_available_ports()
        port_list = [p['device'] for p in ports]
        
        self.com_combo['values'] = port_list
        
        # Auto-select CH340 if available
        ch340_ports = [p for p in ports if p['is_ch340']]
        if ch340_ports and not self.is_connected:
            self.com_var.set(ch340_ports[0]['device'])
        elif port_list and not self.com_var.get():
            self.com_var.set(port_list[0])
    
    def connect_arduino(self):
        """Connect to Arduino"""
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
            
            # Disable server entry when connected
            self.server_entry.config(state=tk.DISABLED)
            
            self.status_label.config(text=f"🟢 Kết nối {com_port}", foreground="green")
            
            # Start reading thread
            self.thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.thread.start()
            
        except serial.SerialException as e:
            self.is_connected = False
            self.running = False
            self.status_label.config(text="⚫ Lỗi kết nối", foreground="red")
    
    def disconnect_arduino(self):
        """Disconnect from Arduino"""
        self.user_disconnected = True
        self.running = False
        if self.ser:
            self.ser.close()
        
        self.is_connected = False
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.com_combo.config(state="readonly")
        
        # Enable server entry when disconnected
        self.server_entry.config(state=tk.NORMAL)
        
        self.status_label.config(text="⚫ Chưa kết nối", foreground="red")
    
    def read_serial_data(self):
        """Read data from Arduino in separate thread"""
        buffer = ""
        
        while self.running and self.ser:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            try:
                                json_data = json.loads(line)
                                
                                # Display in table
                                self.root.after(0, lambda d=json_data: self.format_data_display(d))
                                
                                # Send to server if configured
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
        """Start auto-monitor thread for detecting Arduino"""
        self.monitor_thread = threading.Thread(target=self.auto_monitor_arduino, daemon=True)
        self.monitor_thread.start()
    
    def auto_monitor_arduino(self):
        """Continuously monitor and auto-connect to Arduino with CH340"""
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
                print(f"Monitor error: {e}")
                threading.Event().wait(2)
    
    def send_to_server(self, data):
        """Send data to server"""
        server_url = self.server_url_var.get()
        if not server_url or server_url == "http://127.0.0.1:8000/api/voltages":
            return
        
        try:
            response = requests.post(server_url, json=data, timeout=2)
        except:
            pass
    
    def save_settings(self):
        """Save settings to config file"""
        try:
            settings = {
                'server_url': self.server_url_var.get(),
                'auto_connect': self.auto_connect_var.get(),
                'last_com': self.com_var.get()
            }
            
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    
    def load_settings(self):
        """Load settings from config file"""
        self.auto_connect_var = tk.BooleanVar(value=True)
        self.server_url_var = tk.StringVar(value="http://127.0.0.1:8000/api/voltages")
        self.com_var = tk.StringVar()
        
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.server_url_var.set(settings.get('server_url', "http://127.0.0.1:8000/api/voltages"))
                self.auto_connect_var.set(settings.get('auto_connect', True))
                self.com_var.set(settings.get('last_com', ''))
        except FileNotFoundError:
            # First run - save default settings with auto_connect = True
            self.save_settings()
    
    def on_closing(self):
        """Handle window closing"""
        self.user_disconnected = True  # Mark disconnection as user-initiated
        self.running = False
        if self.is_connected and self.ser:
            self.disconnect_arduino()
        self.save_settings()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ArduinoDataLogger(root)
    root.mainloop()

if __name__ == "__main__":
    main()
