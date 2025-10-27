"""
右侧主面板 - 容器
"""

import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
from typing import Optional, Callable, Dict, Any

from src.config.settings import settings
from src.api.monkey_ocr_client import MonkeyOCRClient
from .right_panel_sections.api_section import ApiSection
from .right_panel_sections.page_section import PageSection
from .right_panel_sections.control_section import ControlSection
from .right_panel_sections.progress_section import ProgressSection
from .right_panel_sections.log_section import LogSection

class RightPanel(ctk.CTkFrame):
    """右侧功能选项和配置的主容器面板"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)

        # Unpack kwargs
        self.ocr_client = kwargs.get('ocr_client')
        self.on_start_processing = kwargs.get('on_start_processing')
        self.on_theme_changed = kwargs.get('on_theme_changed')
        self.get_current_page = kwargs.get('get_current_page')

        self._create_widgets()

    def _create_widgets(self):
        """创建紧凑的标签页布局"""
        # 顶部工具栏 - API状态和主题;
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        # 紧凑的主题选择器;
        theme_combo = ctk.CTkComboBox(
            header_frame,
            values=["system", "light", "dark"],
            width=70,
            height=28,
            command=self.on_theme_changed
        )
        theme_combo.set(settings.get("ui.theme", "system"))
        theme_combo.grid(row=0, column=0, sticky="w")

        # API状态指示器;
        self.api_status_label = ctk.CTkLabel(
            header_frame,
            text="API: 未连接",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        self.api_status_label.grid(row=0, column=2, sticky="e")

        # 标签页容器;
        self.tabview = ctk.CTkTabview(self, width=200, height=500)
        self.tabview.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

        # 创建标签页;
        self.tabview.add("处理")
        self.tabview.add("API")
        self.tabview.add("日志")

        # 处理标签页 - 整合页面选择、控制和进度;
        process_tab = self.tabview.tab("处理")
        self.page_section = PageSection(process_tab, self.get_current_page)
        self.page_section.pack(fill="x", padx=5, pady=5)

        self.control_section = ControlSection(process_tab, self._start_processing_proxy)
        self.control_section.pack(fill="x", padx=5, pady=5)

        self.progress_section = ProgressSection(process_tab)
        self.progress_section.pack(fill="x", padx=5, pady=5)

        # API标签页;
        api_tab = self.tabview.tab("API")
        self.api_section = ApiSection(api_tab, self.ocr_client)
        self.api_section.pack(fill="both", expand=True, padx=5, pady=5)

        # 日志标签页;
        log_tab = self.tabview.tab("日志")
        self.log_section = LogSection(log_tab)
        self.log_section.pack(fill="both", expand=True, padx=5, pady=5)

    def _start_processing_proxy(self):
        """处理开始前的代理，收集所有配置"""
        if self.control_section.is_processing:
            messagebox.showwarning("警告", "正在处理中，请等待完成")
            return

        try:
            start_page, end_page = self.page_section.get_page_range()
            config = {
                "start_page": start_page,
                "end_page": end_page,
                "mode": "Document",
                "total_pages": end_page - start_page + 1
            }
            self.control_section.set_processing_state(True)
            self.progress_section.update_progress(0, "准备中...")
            self.on_start_processing(config)
        except ValueError:
            return

    def processing_completed(self, success: bool):
        """处理完成"""
        self.control_section.set_processing_state(False)
        if success:
            self.progress_section.update_progress(1, "处理完成")
        else:
            self.progress_section.update_progress(0, "处理失败")

    def update_page_range(self, max_pages: int):
        self.page_section.update_page_range(max_pages)

    def update_progress(self, progress: float, message: str):
        self.progress_section.update_progress(progress, message)
    
    def add_log(self, level: str, message: str, detail: str = None):
        """Add log message through logging system"""
        import logging
        logger = logging.getLogger('src')
        
        # Format message with detail if provided
        full_message = f"{message}: {detail}" if detail else message
        
        # Log at appropriate level
        if level.upper() == "DEBUG":
            logger.debug(full_message)
        elif level.upper() == "INFO":
            logger.info(full_message)
        elif level.upper() == "WARNING":
            logger.warning(full_message)
        elif level.upper() == "ERROR":
            logger.error(full_message)
        else:
            logger.info(full_message)
    
    def update_current_page(self, page_number: int):
        """Update current page number in page section"""
        if hasattr(self.page_section, 'update_current_page'):
            self.page_section.update_current_page(page_number)
    
    def update_api_status(self, status: str, message: str):
        """Update API status in both the header and API section"""
        # 更新顶部API状态指示器;
        if hasattr(self, 'api_status_label'):
            status_colors = {
                "healthy": ("green", "green"),
                "testing": ("orange", "orange"),
                "error": ("red", "red")
            }
            color = status_colors.get(status, ("gray50", "gray50"))
            status_text = message[:20] + "..." if len(message) > 20 else message
            self.api_status_label.configure(text=f"API: {status_text}", text_color=color)

        # 更新API区域详细状态;
        if hasattr(self.api_section, 'update_status_from_external'):
            self.api_section.update_status_from_external(status, message)
    
    def refresh_api_section(self):
        """刷新API配置区域显示"""
        if hasattr(self.api_section, 'refresh_api_display'):
            self.api_section.refresh_api_display()
