"""
main.py
Entry point: python main.py
"""
import tkinter as tk
from app import DoTiepDiaApp


def main():
    root = tk.Tk()
    app = DoTiepDiaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()