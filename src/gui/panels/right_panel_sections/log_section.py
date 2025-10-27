""

import customtkinter as ctk
import tkinter as tk
import logging

from src.config.settings import settings
from src.utils.file_utils import get_temp_dir_info

class LogSection(ctk.CTkFrame):
    """日志显示区域"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_widgets()
        self._setup_logging()

    def _create_widgets(self):
        """创建紧凑的界面组件"""
        # 紧凑的工具栏;
        log_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_header_frame.pack(fill="x", padx=5, pady=5)
        log_header_frame.grid_columnconfigure(0, weight=1)

        self.log_level_var = tk.StringVar(value=settings.get("logging.level", "INFO"))
        self.log_level_combo = ctk.CTkComboBox(
            log_header_frame,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self.log_level_var,
            width=70,
            height=24,
            command=self._on_log_level_change
        )
        self.log_level_combo.grid(row=0, column=0, padx=2, sticky="w")

        self.clear_log_btn = ctk.CTkButton(
            log_header_frame,
            text="清空",
            width=50,
            height=24,
            command=self.clear_log
        )
        self.clear_log_btn.grid(row=0, column=1, padx=2)

        # 日志文本区域;
        self.log_text = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=9)
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=2)

    def _setup_logging(self):
        """设置日志处理器"""
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                try:
                    msg = self.format(record)
                    if self.text_widget.winfo_exists():
                        self.text_widget.insert("end", msg + "\n")
                        self.text_widget.see("end")
                except:
                    pass

        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
        self.log_handler = GUILogHandler(self.log_text)
        self.log_handler.setFormatter(formatter)
        self.log_handler.setLevel(getattr(logging, self.log_level_var.get()))

        logger = logging.getLogger('src')
        logger.addHandler(self.log_handler)
        logger.setLevel(logging.DEBUG)

    def _on_log_level_change(self, value: str):
        """日志级别变化回调"""
        settings.set("logging.level", value)
        self.log_handler.setLevel(getattr(logging, value))

    def clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", "end")
        try:
            temp_info = get_temp_dir_info()
            if temp_info["exists"] and temp_info["file_count"] > 0:
                size_mb = temp_info["total_size"] / (1024 * 1024)
                logging.getLogger('src').info(f"临时目录: {temp_info['file_count']} 个文件, {size_mb:.1f}MB")
            else:
                logging.getLogger('src').info("临时目录: 无文件")
        except Exception as e:
            logging.getLogger('src').error(f"获取临时目录信息失败: {e}")
