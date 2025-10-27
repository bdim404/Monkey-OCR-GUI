"""
API配置区域子面板
"""

import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
import threading
from typing import Optional, Callable

from src.config.settings import settings
from src.api.monkey_ocr_client import MonkeyOCRClient, APIError

class ApiSection(ctk.CTkFrame):
    """API配置区域"""
    
    def __init__(self, parent, ocr_client: MonkeyOCRClient):
        super().__init__(parent)
        self.ocr_client = ocr_client
        
        self.grid_columnconfigure(2, weight=1)
        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        """创建紧凑的界面组件"""
        url_label = ctk.CTkLabel(self, text="API地址:", font=ctk.CTkFont(size=12))
        url_label.grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")

        # Protocol dropdown;
        self.protocol_combo = ctk.CTkComboBox(
            self,
            values=["https://", "http://"],
            width=80,
            height=24,
            state="readonly"
        )
        self.protocol_combo.grid(row=1, column=0, padx=(5, 2), pady=2, sticky="w")
        self.protocol_combo.set("https://")
        self.protocol_combo.configure(command=self._on_protocol_change)

        # Domain entry;
        self.domain_entry = ctk.CTkEntry(self, placeholder_text="api.example.com", height=24)
        self.domain_entry.grid(row=1, column=1, padx=2, pady=2, sticky="ew")
        self.domain_entry.bind('<KeyRelease>', self._on_domain_change)

        self.test_btn = ctk.CTkButton(self, text="测试", width=50, height=24, command=self.test_connection)
        self.test_btn.grid(row=1, column=2, padx=(2, 5), pady=2)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=2, sticky="ew")

        self.status_indicator = ctk.CTkLabel(status_frame, text="●", font=ctk.CTkFont(size=12), text_color="gray")
        self.status_indicator.grid(row=0, column=0, padx=(0, 3))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="未测试",
            text_color="gray",
            font=ctk.CTkFont(size=10)
        )
        self.status_label.grid(row=0, column=1, sticky="w")

    def _load_settings(self):
        """加载设置"""
        api_url = settings.get("api.base_url", "")
        if api_url:
            self._parse_existing_url(api_url)

    def _parse_existing_url(self, url: str):
        """Parse existing URL into protocol and domain components"""
        if not url:
            return

        # Parse existing URL to populate fields;
        if url.startswith("https://"):
            self.protocol_combo.set("https://")
            domain = url[8:]  # Remove 'https://' prefix;
        elif url.startswith("http://"):
            self.protocol_combo.set("http://")
            domain = url[7:]   # Remove 'http://' prefix;
        else:
            # Fallback: assume https and use full string as domain;
            self.protocol_combo.set("https://")
            domain = url

        # Set domain in entry field;
        self.domain_entry.delete(0, tk.END)
        self.domain_entry.insert(0, domain)

    def _on_protocol_change(self, selected_value=None):
        """Handle protocol dropdown changes"""
        self._save_current_config()
        self._update_connection_status("unknown", "未测试")

    def _on_domain_change(self, event=None):
        """Handle domain entry changes"""
        self._save_current_config()
        self._update_connection_status("unknown", "未测试")

    def _save_current_config(self):
        """Save current configuration to settings"""
        url = self._build_api_url()
        if url:
            settings.set("api.base_url", url)

    def _build_api_url(self) -> str:
        """Build complete API URL from protocol and domain"""
        protocol = self.protocol_combo.get()
        domain = self.domain_entry.get().strip()

        if not domain:
            return ""

        # Check if domain already contains port;
        if ':' in domain:
            # User specified custom port, use as-is;
            return f"{protocol}{domain}"
        else:
            # No port specified, use standard behavior;
            return f"{protocol}{domain}"

    def test_connection(self):
        """测试API连接"""
        # Build and save current configuration;
        url = self._build_api_url()
        if not url:
            messagebox.showwarning(
                "输入错误",
                "请先输入域名地址",
                parent=self.winfo_toplevel()
            )
            return

        # Save configuration before testing;
        settings.set("api.base_url", url)

        self.test_btn.configure(state="disabled", text="测试中...")
        self._update_connection_status("testing", "连接中...")

        def _test():
            try:
                result = self.ocr_client.health_check()
                message = result.get("message", "服务正常")
                full_message = result.get("data", {}).get("message", message) if isinstance(result, dict) else message
                self.after(0, lambda: self._on_test_success(full_message))
            except APIError as e:
                error_message = str(e)
                self.after(0, lambda: self._on_test_failure(error_message))
            finally:
                self.after(0, lambda: self.test_btn.configure(state="normal", text="测试"))

        threading.Thread(target=_test, daemon=True).start()

    def _update_connection_status(self, status: str, message: str):
        """更新连接状态"""
        color_map = {
            "healthy": "green",
            "error": "red",
            "testing": "orange",
            "unknown": "gray"
        }
        color = color_map.get(status, "gray")
        self.status_indicator.configure(text_color=color)
        self.status_label.configure(text=message, text_color=color)
    
    def update_status_from_external(self, status: str, message: str):
        """从外部更新API连接状态，用于启动检查"""
        self._update_connection_status(status, message)
    
    def _on_test_success(self, message: str):
        """处理测试成功"""
        self._update_connection_status("healthy", "✓ 连接成功")

        # Show success message box;
        messagebox.showinfo(
            "API测试成功",
            f"API连接测试成功！\n\n{message}\n\nAPI现在已可以正常使用。",
            parent=self.winfo_toplevel()
        )

    def _on_test_failure(self, error_msg: str):
        """处理测试失败"""
        short_msg = error_msg[:30] + "..." if len(error_msg) > 30 else error_msg
        self._update_connection_status("error", f"✗ {short_msg}")

        # Show error message box with detailed information;
        messagebox.showerror(
            "API测试失败",
            f"API连接测试失败：\n\n{error_msg}\n\n建议检查：\n" +
            "• API地址是否正确且可访问\n" +
            "• 网络连接是否正常\n" +
            "• API服务是否正在运行\n" +
            "• 防火墙或代理设置是否阻塞了连接",
            parent=self.winfo_toplevel()
        )

    def refresh_api_display(self):
        """刷新API地址显示，重新从设置中加载"""
        self._load_settings()
