"""
API Configuration Dialog

Simple dialog for guiding users to configure API settings during startup.
"""

import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as messagebox
import threading
from typing import Optional, Callable

from src.config.settings import settings
from src.api.monkey_ocr_client import MonkeyOCRClient, APIError


class ApiConfigDialog(ctk.CTkToplevel):
    """API configuration dialog for first-time setup"""
    
    def __init__(self, parent, on_configured: Optional[Callable] = None):
        super().__init__(parent)
        
        self.on_configured = on_configured
        self.ocr_client = MonkeyOCRClient()
        self.config_saved = False
        
        self._setup_window()
        self._create_widgets()
        self._center_window()
        
        # Make dialog modal;
        self.transient(parent)
        self.grab_set()
        
        # Load existing configuration if available;
        self._load_existing_config()

        # Focus on domain entry;
        self.after(100, lambda: self.domain_entry.focus())
    
    def _setup_window(self):
        """Setup window properties"""
        self.title("需要配置API")
        self.geometry("550x300")
        self.resizable(False, False)
        
        # Configure grid weights;
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Header frame;
        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="API 配置",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=15)

        desc_label = ctk.CTkLabel(
            header_frame,
            text="请配置 Monkey OCR API 地址以继续使用：",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        desc_label.grid(row=1, column=0, pady=(0, 15))

        # Main content frame;
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content_frame.grid_columnconfigure(2, weight=1)

        # URL input row;
        url_label = ctk.CTkLabel(content_frame, text="API地址:")
        url_label.grid(row=0, column=0, padx=(15, 10), pady=15, sticky="w")

        # Protocol dropdown;
        self.protocol_combo = ctk.CTkComboBox(
            content_frame,
            values=["https://", "http://"],
            width=100,
            state="readonly"
        )
        self.protocol_combo.grid(row=0, column=1, padx=(0, 5), pady=15)
        self.protocol_combo.set("https://")  # Default to HTTPS;
        self.protocol_combo.configure(command=self._on_protocol_change)

        # Domain input;
        self.domain_entry = ctk.CTkEntry(
            content_frame,
            placeholder_text="api.example.com",
            height=35
        )
        self.domain_entry.grid(row=0, column=2, padx=(0, 10), pady=15, sticky="ew")
        self.domain_entry.bind('<KeyRelease>', self._on_domain_change)
        self.domain_entry.bind('<Return>', lambda e: self._test_and_save())
        
        # Status display;
        status_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        status_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=10, sticky="ew")

        self.status_indicator = ctk.CTkLabel(
            status_frame,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.status_indicator.grid(row=0, column=0, padx=(0, 8))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="请输入域名地址",
            text_color="gray70"
        )
        self.status_label.grid(row=0, column=1, sticky="w")

        # Button frame;
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        button_frame.grid_columnconfigure(0, weight=1)

        # Action buttons;
        self.save_btn = ctk.CTkButton(
            button_frame,
            text="测试并保存",
            width=140,
            command=self._test_and_save,
            state="disabled"
        )
        self.save_btn.grid(row=0, column=1, padx=(10, 0), pady=10)

        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="暂时跳过",
            width=100,
            fg_color="gray50",
            hover_color="gray40",
            command=self._skip_configuration
        )
        self.cancel_btn.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="e")
    
    def _center_window(self):
        """Center dialog on parent window"""
        self.update_idletasks()  # Ensure geometry is calculated;
        
        # Get parent window position and size;
        parent = self.master
        if parent:
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
            
            # Calculate center position;
            dialog_width = self.winfo_width()
            dialog_height = self.winfo_height()
            
            x = parent_x + (parent_width // 2) - (dialog_width // 2)
            y = parent_y + (parent_height // 2) - (dialog_height // 2)
            
            self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _load_existing_config(self):
        """Load and parse existing configuration"""
        existing_url = settings.get("api.base_url", "").strip()
        if existing_url:
            self._parse_existing_url(existing_url)

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

        # Validate inputs after loading;
        self._validate_inputs()

    def _on_protocol_change(self, selected_value=None):
        """Handle protocol dropdown changes"""
        self._validate_inputs()

    def _on_domain_change(self, event=None):
        """Handle domain entry changes"""
        self._validate_inputs()

    def _validate_inputs(self):
        """Validate input fields and update UI state"""
        domain = self.domain_entry.get().strip()
        if domain:
            self._update_status("unknown", "点击'测试并保存'进行验证", "gray")
            self.save_btn.configure(state="normal")
        else:
            self._update_status("unknown", "请输入域名地址", "gray")
            self.save_btn.configure(state="disabled")

        # Reset skip button highlighting;
        self._reset_skip_highlighting()
    
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
            # No port specified, add standard ports;
            if protocol == "https://":
                # For HTTPS, we typically don't need to specify port 443 explicitly;
                return f"{protocol}{domain}"
            else:
                # For HTTP, we typically don't need to specify port 80 explicitly;
                return f"{protocol}{domain}"

    def _test_and_save(self):
        """Test API connection and save if successful"""
        domain = self.domain_entry.get().strip()
        if not domain:
            return

        # Build complete URL;
        url = self._build_api_url()
        if not url:
            return

        # Temporarily save URL for testing;
        settings.set("api.base_url", url)

        # Update UI state;
        self.save_btn.configure(state="disabled", text="测试中...")
        self._update_status("testing", "正在测试连接...", "orange")

        def _test_thread():
            try:
                result = self.ocr_client.health_check()
                message = result.get("data", {}).get("message", "Connection successful")
                self.after(0, lambda: self._on_test_success(message, url))
            except APIError as e:
                error_msg = str(e)
                self.after(0, lambda: self._on_test_failure(error_msg))
            finally:
                self.after(0, lambda: self.save_btn.configure(state="normal", text="测试并保存"))

        threading.Thread(target=_test_thread, daemon=True).start()
    
    def _on_test_success(self, message: str, url: str):
        """Handle successful connection test"""
        self._update_status("success", f"✓ 连接成功", "green")

        # Save configuration permanently;
        settings.set("api.base_url", url)
        self.config_saved = True

        # Show success message and close dialog;
        messagebox.showinfo(
            "连接成功",
            f"API连接测试成功！\n\n{message}\n\n配置已保存，现在可以正常使用。",
            parent=self
        )

        # Notify parent of successful configuration;
        if self.on_configured:
            self.on_configured(url)

        # Close dialog automatically after successful test and save;
        self._close_dialog()
    
    def _on_test_failure(self, error_msg: str):
        """Handle failed connection test"""
        short_msg = error_msg[:60] + "..." if len(error_msg) > 60 else error_msg
        self._update_status("error", f"✗ 连接失败: {short_msg}", "red")
        self.save_btn.configure(state="disabled")

        # Highlight skip button and show error dialog;
        self._highlight_skip_option()

        # Show error message with suggestions;
        result = messagebox.showerror(
            "连接失败",
            f"API连接测试失败：\n\n{error_msg}\n\n建议检查：\n" +
            "• API地址是否正确\n" +
            "• 网络连接是否正常\n" +
            "• API服务是否可用\n\n" +
            "您可以点击'暂时跳过'继续使用程序，稍后再配置API。",
            parent=self
        )
    
    def _update_status(self, status: str, message: str, color: str):
        """Update status display"""
        self.status_indicator.configure(text_color=color)
        self.status_label.configure(text=message, text_color=color)
    
    
    def _skip_configuration(self):
        """Skip configuration for now"""
        self.config_saved = False
        self._close_dialog()
    
    def _highlight_skip_option(self):
        """Highlight the skip button when test fails"""
        self.cancel_btn.configure(
            fg_color=("#FF6B6B", "#FF5252"),
            hover_color=("#FF5252", "#FF1744"),
            text="暂时跳过 ⚡"
        )

    def _reset_skip_highlighting(self):
        """Reset skip button to normal appearance"""
        self.cancel_btn.configure(
            fg_color="gray50",
            hover_color="gray40",
            text="暂时跳过"
        )

    def _close_dialog(self):
        """Close dialog and release grab"""
        self.grab_release()
        self.destroy()