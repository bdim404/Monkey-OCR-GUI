"""
进度显示区域子面板
"""

import customtkinter as ctk

class ProgressSection(ctk.CTkFrame):
    """进度显示区域"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)
        self._create_widgets()

    def _create_widgets(self):
        """创建紧凑的界面组件"""
        self.progress_bar = ctk.CTkProgressBar(self, height=16)
        self.progress_bar.pack(fill="x", padx=5, pady=5)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self,
            text="就绪",
            text_color="gray",
            font=ctk.CTkFont(size=10)
        )
        self.progress_label.pack(fill="x", padx=5, pady=2)

    def update_progress(self, progress: float, message: str = ""):
        """更新进度"""
        self.progress_bar.set(progress)
        if message:
            self.progress_label.configure(text=message)
