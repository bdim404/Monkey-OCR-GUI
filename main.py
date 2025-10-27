#!/usr/bin/env python3
"""
Monkey OCR for Windows - Main Application
基于 Monkey OCR API 的 Windows 图形化工具
"""

import atexit
import os
import sys

import customtkinter as ctk

# 设置正确的路径，支持 PyInstaller 打包环境
if getattr(sys, "frozen", False):
    # PyInstaller 打包环境
    BASE_DIR = os.path.dirname(sys.executable)
    # 将打包的源码目录添加到 Python 路径
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
else:
    # 开发环境
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # Add the current directory to Python path
    sys.path.append(BASE_DIR)

# 设置当前工作目录;
os.chdir(BASE_DIR)

from src.config.settings import settings
from src.gui.main_window import MainWindow
from src.utils.file_utils import cleanup_temp_files


def main():
    """主程序入口"""
    try:
        # 注册退出时的清理函数;
        if settings.get("cache.cleanup_on_exit", True):
            atexit.register(cleanup_temp_files)

        # 清理过旧的临时文件（启动时）
        if settings.get("cache.auto_cleanup", True):
            cleanup_temp_files(older_than_hours=24)  # 清理24小时以上的文件

        # 设置 CustomTkinter 外观 - 支持动态主题切换
        theme = settings.get("ui.theme", "system")
        ctk.set_appearance_mode(theme)  # 可选: "System", "Dark", "Light"
        ctk.set_default_color_theme("blue")  # 可选: "blue", "green", "dark-blue"

        # 创建并运行应用程序
        app = MainWindow()
        app.run()

    except Exception as e:
        # 在 exe 环境中显示错误信息；
        if getattr(sys, "frozen", False):
            import tkinter.messagebox as messagebox

            messagebox.showerror("错误", f"程序启动失败：\n{str(e)}")
        else:
            print(f"程序启动失败: {e}")
            raise


if __name__ == "__main__":
    main()
