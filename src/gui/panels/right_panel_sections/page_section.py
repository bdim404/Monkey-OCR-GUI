"""
页面选择区域子面板
"""

import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
from typing import Optional, Callable

class PageSection(ctk.CTkFrame):
    """页面选择区域"""
    
    def __init__(self, parent, get_current_page_func: Callable[[], int]):
        super().__init__(parent)
        self.get_current_page_func = get_current_page_func
        self.max_pages = 1
        
        self.grid_columnconfigure(1, weight=1)
        self._create_widgets()

    def _create_widgets(self):
        """创建紧凑的界面组件"""
        # 页面范围输入 - 单行布局;
        range_frame = ctk.CTkFrame(self, fg_color="transparent")
        range_frame.pack(fill="x", padx=5, pady=5)
        range_frame.grid_columnconfigure(1, weight=1)
        range_frame.grid_columnconfigure(3, weight=1)

        range_label = ctk.CTkLabel(range_frame, text="范围:", font=ctk.CTkFont(size=12))
        range_label.grid(row=0, column=0, padx=(0, 5), sticky="w")

        self.start_page_entry = ctk.CTkEntry(range_frame, width=50, height=24, placeholder_text="1")
        self.start_page_entry.grid(row=0, column=1, padx=2, sticky="ew")

        dash_label = ctk.CTkLabel(range_frame, text="至", font=ctk.CTkFont(size=12))
        dash_label.grid(row=0, column=2, padx=2)

        self.end_page_entry = ctk.CTkEntry(range_frame, width=50, height=24, placeholder_text="1")
        self.end_page_entry.grid(row=0, column=3, padx=2, sticky="ew")

        # 快捷按钮 - 紧凑的单行布局;
        quick_frame = ctk.CTkFrame(self, fg_color="transparent")
        quick_frame.pack(fill="x", padx=5, pady=2)
        quick_frame.grid_columnconfigure(0, weight=1)
        quick_frame.grid_columnconfigure(1, weight=1)

        self.current_page_btn = ctk.CTkButton(
            quick_frame,
            text="当前页",
            width=80,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.select_current_page
        )
        self.current_page_btn.grid(row=0, column=0, padx=2, sticky="ew")

        self.all_pages_btn = ctk.CTkButton(
            quick_frame,
            text="全部页",
            width=80,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.select_all_pages
        )
        self.all_pages_btn.grid(row=0, column=1, padx=2, sticky="ew")

    def update_page_range(self, max_pages: int):
        """更新页面范围"""
        self.max_pages = max_pages
        self.end_page_entry.configure(placeholder_text=str(max_pages))
        if not self.start_page_entry.get():
            self.start_page_entry.insert(0, "1")
        if not self.end_page_entry.get():
            self.end_page_entry.delete(0, tk.END)
            self.end_page_entry.insert(0, str(max_pages))

    def select_current_page(self):
        """选择当前页"""
        current_page = self.get_current_page_func()
        self.start_page_entry.delete(0, tk.END)
        self.start_page_entry.insert(0, str(current_page))
        self.end_page_entry.delete(0, tk.END)
        self.end_page_entry.insert(0, str(current_page))

    def select_all_pages(self):
        """选择所有页"""
        self.start_page_entry.delete(0, tk.END)
        self.start_page_entry.insert(0, "1")
        self.end_page_entry.delete(0, tk.END)
        self.end_page_entry.insert(0, str(self.max_pages))

    def get_page_range(self) -> tuple[int, int]:
        """获取页面范围，带详细验证"""
        try:
            start_text = self.start_page_entry.get().strip()
            end_text = self.end_page_entry.get().strip()
            
            # 处理空值
            if not start_text:
                start = 1
            else:
                start = int(start_text)
                
            if not end_text:
                end = self.max_pages
            else:
                end = int(end_text)
            
            # 详细的范围验证
            if start < 1:
                raise ValueError(f"起始页码必须大于等于1，当前输入：{start}")
            if end < 1:
                raise ValueError(f"结束页码必须大于等于1，当前输入：{end}")
            if start > self.max_pages:
                raise ValueError(f"起始页码不能超过最大页数 {self.max_pages}，当前输入：{start}")
            if end > self.max_pages:
                raise ValueError(f"结束页码不能超过最大页数 {self.max_pages}，当前输入：{end}")
            if start > end:
                raise ValueError(f"起始页码({start})不能大于结束页码({end})")
                
            return start, end
            
        except ValueError as e:
            if "invalid literal for int()" in str(e):
                messagebox.showerror("错误", "页码必须为整数")
            else:
                messagebox.showerror("错误", str(e))
            raise

    def update_current_page(self, page_number: int):
        """Update current page and automatically select it for processing"""
        if 1 <= page_number <= self.max_pages:
            self.select_current_page()
