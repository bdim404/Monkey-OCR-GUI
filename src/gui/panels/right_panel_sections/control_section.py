"""
处理控制区域子面板
"""

import customtkinter as ctk
from typing import Callable

class ControlSection(ctk.CTkFrame):
    """处理控制区域"""
    
    def __init__(self, parent, start_processing_callback: Callable):
        super().__init__(parent)
        self.start_processing_callback = start_processing_callback
        self.is_processing = False
        self._create_widgets()

    def _create_widgets(self):
        """创建紧凑的界面组件"""
        self.start_btn = ctk.CTkButton(
            self,
            text="开始处理",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=self.start_processing_callback
        )
        self.start_btn.pack(fill="x", padx=5, pady=5)

    def set_processing_state(self, is_processing: bool):
        """设置处理状态"""
        self.is_processing = is_processing
        if is_processing:
            self.start_btn.configure(state="disabled", text="处理中...")
        else:
            self.start_btn.configure(state="normal", text="开始处理")
