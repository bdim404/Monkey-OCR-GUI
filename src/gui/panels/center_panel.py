"中间面板 - 结果显示和编辑"

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
import markdown2
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import get_formatter_by_name
try:
    from tkinterweb import HtmlFrame
    TKINTERWEB_AVAILABLE = True
except ImportError:
    from tkhtmlview import HTMLScrolledText
    TKINTERWEB_AVAILABLE = False
import jsbeautifier
import os
from typing import Optional, Dict, Any
import io
from PIL import Image
from ..styles.content_styles import ContentStyles
from ..renderers.enhanced_markdown_renderer import enhanced_markdown



class CenterPanel(ctk.CTkFrame):
    """中间结果显示和编辑面板"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.current_content = ""
        self.current_format = "markdown"  # Fixed to markdown only
        self.is_source_mode = False
        self.current_results = {}  # 存储多页结果
        self.current_page = 1
        self.total_pages = 1  # 总页数，用于页面导航显示
        
        self.current_html_viewer = None  # Keep reference to current HTML viewer
        
        # Real-time preview settings
        self.preview_delay = 1000  # milliseconds
        self.preview_timer_id = None
        self.last_content = ""
        
        # 配置网格权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # 内容显示区域可拉伸
        
        self._create_widgets()
        
    def _create_widgets(self):
        """创建界面组件"""
        # 顶部控制栏
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self.control_frame.grid_columnconfigure(2, weight=1)
        
        # 标题
        title = ctk.CTkLabel(
            self.control_frame, 
            text="识别结果", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # 显示模式切换滑块
        self.mode_switch = ctk.CTkSwitch(
            self.control_frame,
            text="源码模式",
            width=100,
            command=self.toggle_display_mode,
            onvalue=1,
            offvalue=0
        )
        self.mode_switch.grid(row=0, column=1, padx=5, pady=5)
        
        
        # 页面导航已移除，只使用左侧面板的翻页功能
        
        # 内容显示区域
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        
        # 初始显示占位符
        self._create_placeholder()
        
        # 底部导出栏
        self.export_frame = ctk.CTkFrame(self)
        self.export_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")
        self.export_frame.grid_columnconfigure(1, weight=1)
        
        # 导出按钮
        self.export_current_btn = ctk.CTkButton(
            self.export_frame,
            text="导出当前页",
            width=100,
            command=self.export_current_page,
            state="disabled"
        )
        self.export_current_btn.grid(row=0, column=0, padx=5, pady=5)
        
        self.export_all_btn = ctk.CTkButton(
            self.export_frame,
            text="导出全部",
            width=80,
            command=self.export_all_pages,
            state="disabled"
        )
        self.export_all_btn.grid(row=0, column=2, padx=5, pady=5)
    
    def _create_placeholder(self):
        """创建占位符显示"""
        # 清空内容区域
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # 创建占位符框架
        placeholder_frame = ctk.CTkFrame(
            self.content_frame,
            corner_radius=15,
            border_width=2,
            border_color=("gray60", "gray40"),
            fg_color="transparent"
        )
        placeholder_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        placeholder_frame.grid_columnconfigure(0, weight=1)
        placeholder_frame.grid_rowconfigure(0, weight=1)
        
        # 占位符文本
        placeholder_label = ctk.CTkLabel(
            placeholder_frame,
            text="识别结果展示\n\n请先上传文件并开始识别",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray50")
        )
        placeholder_label.grid(row=0, column=0, padx=20, pady=20)
    
    def show_placeholder(self, title: str, message: str):
        """显示占位符消息"""
        # 清空内容区域
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # 创建占位符框架
        placeholder_frame = ctk.CTkFrame(
            self.content_frame,
            corner_radius=15,
            border_width=2,
            border_color=("blue", "blue"),
            fg_color="transparent"
        )
        placeholder_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        placeholder_frame.grid_columnconfigure(0, weight=1)
        placeholder_frame.grid_rowconfigure(0, weight=1)
        
        # 占位符文本
        placeholder_label = ctk.CTkLabel(
            placeholder_frame,
            text=f"{title}\n\n{message}",
            font=ctk.CTkFont(size=14),
            text_color=("blue", "lightblue")
        )
        placeholder_label.grid(row=0, column=0, padx=20, pady=20)
    
    def _create_rendered_view(self):
        """创建渲染视图"""
        # 清空内容区域
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        try:
            self._create_markdown_view()
        except Exception as e:
            self._show_error(f"渲染失败: {str(e)}")
    
    def _create_source_view(self):
        """创建源码视图"""
        # 清空内容区域
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # 创建文本编辑器
        self.text_editor = scrolledtext.ScrolledText(
            self.content_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self._get_bg_color(),
            fg=self._get_fg_color(),
            insertbackground=self._get_fg_color()
        )
        self.text_editor.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # 设置内容
        self.text_editor.delete(1.0, tk.END)
        if self.current_content:
            # 美化代码
            try:
                formatted_content = self._beautify_content(self.current_content, self.current_format)
                self.text_editor.insert(1.0, formatted_content)
            except:
                self.text_editor.insert(1.0, self.current_content)
        
        # 绑定内容变化事件
        self.text_editor.bind('<KeyRelease>', self._on_text_change)
    
    def _create_markdown_view(self):
        """在后台线程中创建Markdown渲染视图"""
        # 显示加载提示
        self._show_loading_message("正在渲染内容...")
        
        # 获取当前内容和主题模式
        content = self.current_content
        theme_mode = ctk.get_appearance_mode().lower()
        
        def _render_markdown_worker():
            """后台线程中执行Markdown渲染"""
            try:
                if TKINTERWEB_AVAILABLE:
                    # Use enhanced markdown renderer with LaTeX support
                    enhanced_html = enhanced_markdown.render_to_html(
                        content,
                        theme_mode=theme_mode
                    )
                    
                    # 在主线程中创建UI组件
                    def create_html_frame():
                        try:
                            # 清理加载提示
                            for widget in self.content_frame.winfo_children():
                                widget.destroy()
                            
                            self.current_html_viewer = HtmlFrame(
                                self.content_frame,
                                messages_enabled=False,
                                horizontal_scrollbar="auto"
                            )
                            self.current_html_viewer.load_html(enhanced_html)
                            self.current_html_viewer.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
                        except Exception as e:
                            self._show_error(f"渲染显示失败: {str(e)}")
                    
                    self.after(0, create_html_frame)
                    
                else:
                    # Fallback to basic markdown rendering
                    html_content = markdown2.markdown(
                        content,
                        extras=['fenced-code-blocks', 'tables', 'break-on-newline', 'code-friendly']
                    )
                    
                    enhanced_html = ContentStyles.enhance_markdown_html(
                        html_content,
                        theme_mode=theme_mode
                    )
                    enhanced_html = ContentStyles.add_simple_table_styling(enhanced_html)
                    
                    # 在主线程中创建UI组件
                    def create_html_text():
                        try:
                            # 清理加载提示
                            for widget in self.content_frame.winfo_children():
                                widget.destroy()
                            
                            self.current_html_viewer = HTMLScrolledText(
                                self.content_frame,
                                html=enhanced_html
                            )
                            self.current_html_viewer.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
                        except Exception as e:
                            self._show_error(f"渲染显示失败: {str(e)}")
                    
                    self.after(0, create_html_text)
                    
            except Exception as e:
                # 渲染失败，在主线程显示错误
                error_msg = f"Markdown渲染失败: {str(e)}"
                self.after(0, lambda: self._show_error(error_msg))
        
        # 在后台线程中执行渲染
        import threading
        threading.Thread(target=_render_markdown_worker, daemon=True).start()
    
    

    def _show_loading_message(self, message: str = "正在加载..."):
        """显示加载提示信息"""
        # 清空内容区域
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        loading_label = ctk.CTkLabel(
            self.content_frame,
            text=message,
            text_color=("gray60", "gray40"),
            font=ctk.CTkFont(size=12)
        )
        loading_label.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
    
    def _show_error(self, message: str):
        """显示错误信息"""
        # 清空内容区域
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        error_label = ctk.CTkLabel(
            self.content_frame,
            text=f"错误: {message}",
            text_color="red",
            font=ctk.CTkFont(size=12),
            wraplength=self.winfo_width() - 40
        )
        error_label.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
    
    def toggle_display_mode(self):
        """切换显示模式"""
        if not self.current_content:
            # 如果没有内容，重置滑块状态到预览模式
            self.mode_switch.deselect()
            return
        
        # 根据滑块状态设置模式
        self.is_source_mode = bool(self.mode_switch.get())
        
        if self.is_source_mode:
            self._create_source_view()
        else:
            self._create_rendered_view()
    
    def refresh_theme(self):
        """Refresh content display when theme changes"""
        # Refresh current view
        if not self.is_source_mode and self.current_content:
            self._create_rendered_view()
        elif self.is_source_mode and hasattr(self, 'text_editor'):
            # Update source view colors
            self.text_editor.configure(
                bg=self._get_bg_color(),
                fg=self._get_fg_color(),
                insertbackground=self._get_fg_color()
            )
    
    
    def _on_text_change(self, event=None):
        """文本变化回调 - 支持实时预览"""
        if hasattr(self, 'text_editor'):
            new_content = self.text_editor.get(1.0, tk.END).strip()
            
            # Only update if content actually changed
            if new_content != self.last_content:
                self.current_content = new_content
                self.last_content = new_content
                
                # 更新存储的结果
                if self.current_results and self.current_page in self.current_results:
                    self.current_results[self.current_page]['content'] = self.current_content
                
                # Schedule real-time preview update
                self._schedule_preview_update()
    
    def _schedule_preview_update(self):
        """调度实时预览更新（防抖动）"""
        # Cancel any existing timer
        if self.preview_timer_id:
            self.after_cancel(self.preview_timer_id)
        
        # Schedule new update
        self.preview_timer_id = self.after(self.preview_delay, self._update_preview)
    
    def _update_preview(self):
        """更新实时预览"""
        self.preview_timer_id = None
        
        # Only update if not in source mode and has content
        if not self.is_source_mode and self.current_content.strip():
            try:
                self._create_rendered_view()
            except Exception as e:
                print(f"Preview update failed: {e}")
                # Don't show error to user for preview updates
    
    def _beautify_content(self, content: str, format_type: str) -> str:
        """美化内容格式"""
        try:
            if format_type.lower() == "html":
                # HTML美化
                return jsbeautifier.beautify(content)
            elif format_type.lower() == "json":
                import json
                return json.dumps(json.loads(content), indent=2, ensure_ascii=False)
            else:
                # 其他格式直接返回
                return content
        except:
            return content
    
    def _get_bg_color(self) -> str:
        """获取背景颜色"""
        return "#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#ffffff"
    
    def _get_fg_color(self) -> str:
        """获取前景颜色"""
        return "#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000"
    
    def _get_base_filename(self) -> str:
        """获取原文件的基础文件名(无扩展名)作为导出前缀"""
        try:
            if hasattr(self.master, 'left_panel') and hasattr(self.master.left_panel, 'get_current_file'):
                file_path = self.master.left_panel.get_current_file()
                if file_path:
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    return base_name
            return "exported"
        except Exception:
            return "exported"
    
    def _merge_all_content(self) -> str:
        """合并所有页面内容为单个文件内容"""
        if not self.current_results:
            return ""
        
        merged_content = []
        page_keys = sorted(self.current_results.keys())
        
        for i, page_num in enumerate(page_keys):
            page_data = self.current_results[page_num]
            content = page_data.get("content", "")
            
            if content.strip():
                # 添加页面标题（除了第一页）
                if i > 0:
                    merged_content.append(f"\n\n---\n\n## 第{page_num}页\n\n")
                else:
                    # 第一页只添加页面标题（不加分页符）
                    merged_content.append(f"## 第{page_num}页\n\n")
                
                merged_content.append(content)
        
        return "".join(merged_content)
    
    def show_results(self, results: Dict[int, Dict[str, Any]]):
        """显示识别结果"""
        self.current_results = results
        if results:
            self.current_page = min(results.keys())
            self._load_current_page()
            
            # 启用导出按钮
            self.export_current_btn.configure(state="normal")
            self.export_all_btn.configure(state="normal")
        else:
            self._create_placeholder()
    
    def show_single_result(self, content: str, format_type: str = "markdown"):
        """显示单页结果"""
        self.current_results = {1: {"content": content, "format": "markdown"}}
        self.current_page = 1
        self.current_content = content
        self.current_format = "markdown"
        
        # 同步滑块状态
        self._sync_switch_state()
        
        # 显示内容
        if self.is_source_mode:
            self._create_source_view()
        else:
            self._create_rendered_view()
        
        # 启用导出按钮
        self.export_current_btn.configure(state="normal")
        self.export_all_btn.configure(state="normal")
    
    def _load_current_page(self):
        """加载当前页面内容"""
        if self.current_page in self.current_results:
            page_data = self.current_results[self.current_page]
            self.current_content = page_data.get("content", "")
            self.current_format = "markdown"
            
            # 同步滑块状态
            self._sync_switch_state()
            
            # 显示内容
            if self.is_source_mode:
                self._create_source_view()
            else:
                self._create_rendered_view()
    

    def set_current_page(self, page_number: int):
        """设置并跳转到指定页面"""
        # 始终更新当前页码，保持页面同步
        self.current_page = page_number
        
        # 如果有结果且页面存在，加载内容
        if self.current_results and page_number in self.current_results:
            self._load_current_page()
        
        # 页面导航已移除，只通过左侧面板切换页面
    
    def _sync_switch_state(self):
        """同步滑块状态与内部状态"""
        if self.is_source_mode:
            self.mode_switch.select()
        else:
            self.mode_switch.deselect()
    
    def export_current_page(self):
        """导出当前页"""
        if not self.current_content:
            messagebox.showwarning("警告", "没有内容可导出")
            return
        
        # 生成默认文件名：原文件名_page页码.格式
        base_filename = self._get_base_filename()
        default_filename = f"{base_filename}_page{self.current_page}.{self.current_format}"
        
        # 选择保存文件
        file_types = [
            (f"{self.current_format.upper()} files", f"*.{self.current_format}"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.asksaveasfilename(
            title="导出当前页",
            initialfile=default_filename,
            defaultextension=f".{self.current_format}",
            filetypes=file_types
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_content)
                messagebox.showinfo("成功", f"文件已保存到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {str(e)}")
    
    def export_all_pages(self):
        """导出所有页面为单个合并文件"""
        if not self.current_results:
            messagebox.showwarning("警告", "没有内容可导出")
            return
        
        # 合并所有页面内容
        merged_content = self._merge_all_content()
        if not merged_content.strip():
            messagebox.showwarning("警告", "没有有效内容可导出")
            return
        
        # 固定使用markdown格式
        export_format = "markdown"
        
        # 生成默认文件名：原文件名_merged.格式
        base_filename = self._get_base_filename()
        default_filename = f"{base_filename}_merged.{export_format}"
        
        # 选择保存文件
        file_types = [
            (f"{export_format.upper()} files", f"*.{export_format}"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.asksaveasfilename(
            title="导出合并文件",
            initialfile=default_filename,
            defaultextension=f".{export_format}",
            filetypes=file_types
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(merged_content)
                messagebox.showinfo("成功", f"已合并导出 {len(self.current_results)} 页到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def clear_results(self):
        """清空结果"""
        self.current_content = ""
        self.current_results = {}
        self.current_page = 1
        self.total_pages = 1
        self.is_source_mode = False
        self.mode_switch.deselect()
        
        # 禁用导出按钮
        self.export_current_btn.configure(state="disabled")
        self.export_all_btn.configure(state="disabled")
    
    def set_total_pages(self, total_pages: int):
        """设置总页数"""
        self.total_pages = max(1, total_pages)
        
        # 显示占位符
        self._create_placeholder()
