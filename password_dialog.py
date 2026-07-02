"""
password_dialog.py

Bảo vệ hành động "tắt ứng dụng" bằng mật khẩu. Sai quá 3 lần thì khoá lại
trong suốt phiên chạy — muốn tắt phải dùng Task Manager.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable


class PasswordGate:
    MAX_ATTEMPTS = 3

    def __init__(self, get_password: Callable[[], str]):
        """get_password: hàm trả về mật khẩu đúng hiện tại (đọc từ config)."""
        self._get_password = get_password
        self.failed_attempts = 0
        self.locked = False

    def prompt(self, parent) -> bool:
        """Hiện dialog nhập mật khẩu (blocking, dùng wait_window).
        Trả về True nếu nhập đúng, False nếu sai/huỷ/đã bị khoá."""
        if self.locked:
            messagebox.showerror(
                "Đã bị khóa",
                "Chức năng tắt ứng dụng đã bị khóa.\n"
                "Dùng Task Manager (Ctrl+Shift+Esc) để tắt."
            )
            return False

        dialog = tk.Toplevel(parent)
        dialog.title("Xác nhận tắt ứng dụng")
        dialog.geometry("320x160")
        dialog.resizable(False, False)
        dialog.transient(parent)
        dialog.grab_set()
        dialog.focus_force()
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        dialog.bind('<Alt-F4>', lambda e: "break")

        ttk.Label(dialog, text="Nhập mật khẩu để tắt ứng dụng:",
                  font=("Arial", 10)).pack(pady=12)

        password_var = tk.StringVar()
        pw_entry = ttk.Entry(dialog, textvariable=password_var,
                              show="*", width=28, font=("Arial", 10))
        pw_entry.pack(pady=4)
        pw_entry.focus()

        result = [False]

        def check_password():
            if password_var.get() == self._get_password():
                result[0] = True
                self.failed_attempts = 0
                dialog.destroy()
                return

            self.failed_attempts += 1
            remaining = self.MAX_ATTEMPTS - self.failed_attempts

            if remaining <= 0:
                self.locked = True
                dialog.destroy()
                messagebox.showerror(
                    "Sai mật khẩu 3 lần!",
                    "Tắt ứng dụng đã bị khóa."
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

        parent.wait_window(dialog)
        return result[0]