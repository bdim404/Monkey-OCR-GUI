"""
主窗口界面
"""

import os
import platform
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import customtkinter as ctk

from src.api.monkey_ocr_client import APIError, MonkeyOCRClient
from src.config.settings import settings
from src.gui.dialogs.api_config_dialog import ApiConfigDialog
from src.gui.panels.center_panel import CenterPanel
from src.gui.panels.left_panel import LeftPanel
from src.gui.panels.right_panel import RightPanel


class MainWindow(ctk.CTk):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.settings = settings
        self.ocr_client = MonkeyOCRClient()
        self.results_lock = threading.Lock()  # 线程安全保护共享结果字典

        # 创建主窗口
        self.title("Monkey OCR for Windows")

        # 设置窗口大小和位置
        width = self.settings.get("ui.window_width", 1200)
        height = self.settings.get("ui.window_height", 800)
        self.geometry(f"{width}x{height}")

        # 设置最小窗口大小
        self.minsize(800, 600)

        # 默认全屏显示 - 使用跨平台方法
        self._set_window_maximized()

        # 配置网格权重 - 整个容器可拉伸
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 创建面板
        self._create_panels()

        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 执行启动时检查
        self.after(100, self._perform_startup_checks)

        # 启动字体预加载
        self.after(200, self._preload_fonts)

    def _set_window_maximized(self):
        """Cross-platform window maximization;"""
        try:
            system = platform.system()
            if system == "Windows":
                # Windows: Try zoomed state first, fallback to attributes;
                try:
                    self.state("zoomed")
                except tk.TclError:
                    # Fallback for Windows systems where zoomed doesn't work;
                    try:
                        self.attributes("-zoomed", True)
                    except tk.TclError:
                        # Last resort: manual geometry maximization;
                        self.geometry("{}x{}+0+0".format(self.winfo_screenwidth(), self.winfo_screenheight()))
            elif system == "Darwin":  # macOS
                # macOS: zoomed state works reliably;
                self.state("zoomed")
            else:  # Linux and others
                # Linux: Use zoomed state;
                self.state("zoomed")
        except Exception as e:
            # Fallback: Use the original method if platform detection fails;
            try:
                self.state("zoomed")
            except tk.TclError:
                pass  # Ignore if even the fallback fails;

    def _create_panels(self):
        """创建三个面板，使用单一PanedWindow支持全面拖拽调整"""
        # 创建单一的三面板PanedWindow - 水平分割，支持所有面板调整
        self.main_paned = tk.PanedWindow(
            self,
            orient="horizontal",
            sashwidth=4,  # Reduced width for less visible borders;
            sashrelief="flat",  # Flat relief eliminates 3D white borders;
            bg=self._get_bg_color(),
        )
        self.main_paned.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # 左侧面板 - 文件上传和渲染
        self.left_panel = LeftPanel(
            self.main_paned,
            on_file_selected=self.on_file_selected,
            on_page_changed=self.on_page_changed,
        )

        # 中间面板 - 结果显示
        self.center_panel = CenterPanel(self.main_paned)

        # 右侧面板 - 功能选项
        self.right_panel = RightPanel(
            self.main_paned,
            ocr_client=self.ocr_client,
            on_start_processing=self.on_start_processing,
            on_theme_changed=self.on_theme_changed,
            get_current_page=self.get_current_page,
        )

        # 获取最小宽度配置 - 增加右侧面板最小宽度，减少左侧;
        min_widths = self.settings.get(
            "ui.panel_min_widths", {"left": 220, "center": 400, "right": 200}
        )

        # 添加面板到PanedWindow，设置最小宽度约束
        self.main_paned.add(self.left_panel, minsize=min_widths["left"])
        self.main_paned.add(self.center_panel, minsize=min_widths["center"])
        self.main_paned.add(self.right_panel, minsize=min_widths["right"])

        # 计算并应用默认面板尺寸
        self._apply_default_panel_sizes()

        # 恢复保存的面板位置
        self._restore_panel_positions()

    def _apply_default_panel_sizes(self):
        """计算并应用默认面板尺寸"""
        # 获取窗口宽度（减去边距） - 调整边距计算;
        window_width = self.settings.get("ui.window_width", 1200)
        available_width = window_width - 10  # 减少边距到5px

        # 获取默认比例配置 - 重新平衡面板比例，给右侧更多空间;
        ratios = self.settings.get(
            "ui.panel_ratios", {"left": 0.30, "center": 0.55, "right": 0.15}
        )

        # 计算面板宽度
        left_width = int(available_width * ratios["left"])
        center_width = int(available_width * ratios["center"])

        # 计算分割条位置（累积宽度）
        first_sash = left_width
        second_sash = left_width + center_width

        # 延迟应用尺寸，确保窗口完全初始化
        self.after(50, lambda: self._set_sash_positions(first_sash, second_sash))

    def _set_sash_positions(self, first_sash: int, second_sash: int):
        """设置分割条位置"""
        try:
            self.main_paned.sash_place(0, first_sash, 0)
            self.main_paned.sash_place(1, second_sash, 0)
        except tk.TclError:
            # 如果设置失败，使用默认布局
            pass

    def _get_bg_color(self):
        """获取当前主题的背景颜色"""
        # Use CustomTkinter's actual appearance mode instead of config setting;
        appearance_mode = ctk.get_appearance_mode()
        if appearance_mode == "Dark":
            return "#212121"
        else:
            return "#ebebeb"

    def _restore_panel_positions(self):
        """恢复保存的面板位置（所有三个面板）"""
        try:
            # 尝试恢复新的双分割条位置配置
            sash_positions = self.settings.get("ui.sash_positions", None)

            if sash_positions and len(sash_positions) == 2:
                # 使用新的双分割条配置
                self.after(
                    100,
                    lambda: self._set_sash_positions(
                        sash_positions[0], sash_positions[1]
                    ),
                )
            else:
                # 尝试从旧的单分割条配置迁移
                old_sash_pos = self.settings.get("ui.left_center_sash_position", None)
                if old_sash_pos is not None:
                    # 基于旧位置估算新的双分割条位置
                    window_width = self.settings.get("ui.window_width", 1200)
                    available_width = window_width - 20

                    # 假设旧的分割条位置是左中分割，右侧固定320px
                    first_sash = old_sash_pos
                    second_sash = available_width - 180  # 右侧面板默认15%

                    self.after(
                        100, lambda: self._set_sash_positions(first_sash, second_sash)
                    )

                    # 迁移配置并清理旧配置
                    self.settings.set("ui.sash_positions", [first_sash, second_sash])
                    # 保留旧配置以防回滚需要

        except Exception as e:
            # 如果恢复失败，使用默认比例
            pass

    def on_page_changed(self, page_index: int):
        """页面切换回调，同步所有面板"""
        page_number = page_index + 1

        # 通知中间面板更新页面
        if hasattr(self.center_panel, "set_current_page"):
            self.center_panel.set_current_page(page_number)

        # 通知右侧面板更新当前页面
        if hasattr(self.right_panel, "update_current_page"):
            self.right_panel.update_current_page(page_number)

    def get_current_page(self) -> int:
        """获取当前页面号"""
        if self.left_panel.has_file():
            return self.left_panel.current_page_index + 1  # 页面号从1开始
        return 1

    def on_theme_changed(self, theme: str):
        """主题变化回调"""
        ctk.set_appearance_mode(theme)
        self.settings.set("ui.theme", theme)

        # Update PanedWindow background to match new theme;
        self.main_paned.configure(bg=self._get_bg_color())

        # Refresh center panel content rendering to apply new theme;
        if hasattr(self.center_panel, "refresh_theme"):
            self.center_panel.refresh_theme()

    def _schedule_progress_update(
        self, progress_value: float, processed: int, total: int
    ):
        """线程安全的进度更新调度，避免lambda变量捕获问题"""
        from functools import partial

        # 使用偏函数固定参数，避免闭包变量捕获问题
        update_func = partial(
            self.right_panel.update_progress,
            progress_value,
            f"已处理 {processed}/{total} 页",
        )
        self.after(0, update_func)

    def _schedule_ui_update(self, func, *args, **kwargs):
        """通用的线程安全UI更新调度器"""
        from functools import partial

        if args or kwargs:
            update_func = partial(func, *args, **kwargs)
        else:
            update_func = func
        self.after(0, update_func)

    def _calculate_optimal_workers(self, task_count: int, operation_type: str) -> int:
        """基于系统能力和任务数量计算最优工作线程数"""
        try:
            import psutil

            # 获取系统当前状态 - 使用非阻塞方式获取CPU使用率
            cpu_usage = psutil.cpu_percent(interval=None)  # 非阻塞获取瞬时CPU使用率
            memory = psutil.virtual_memory()
            available_memory_gb = memory.available / (1024**3)

            # 获取基础配置的工作线程数
            base_workers = settings.get_worker_count(operation_type)

            # 基于任务数量调整 - 不需要超过任务数量的线程
            task_based_limit = min(base_workers, task_count)

            # 基于系统负载调整
            load_factor = 1.0
            if cpu_usage > 80:
                load_factor = 0.5  # CPU高负载时减少线程
            elif cpu_usage > 60:
                load_factor = 0.75  # CPU中等负载时适度减少

            # 基于内存状态调整
            memory_factor = 1.0
            if available_memory_gb < 1.0:
                memory_factor = 0.5  # 内存不足时大幅减少线程
            elif available_memory_gb < 2.0:
                memory_factor = 0.75  # 内存紧张时适度减少

            # 计算最终线程数
            optimal_workers = int(task_based_limit * load_factor * memory_factor)

            # 确保至少有1个工作线程，最多不超过配置上限
            min_workers = settings.get("performance.concurrency.min_workers", 2)
            max_workers_limit = settings.get("performance.concurrency.max_workers", 16)

            return max(1, min(max_workers_limit, max(min_workers, optimal_workers)))

        except Exception as e:
            # 如果系统检测失败，回退到基础配置
            self.right_panel.add_log(
                "WARNING", f"线程数计算失败，使用默认配置: {str(e)}"
            )
            return min(settings.get_worker_count(operation_type), task_count)

    def on_file_selected(self, file_path: str, pages: list):
        """文件选择回调"""
        # 更新右侧面板的页数范围
        self.right_panel.update_page_range(len(pages))
        # 清空之前的结果并设置总页数
        self.center_panel.clear_results()
        self.center_panel.set_total_pages(len(pages))

    def on_start_processing(self, config: dict):
        """开始处理回调"""
        if not self.left_panel.has_file():
            tk.messagebox.showwarning("警告", "请先选择文件")
            return

        # 获取当前文件和页面信息
        file_path = self.left_panel.get_current_file()
        pages = self.left_panel.get_current_pages()

        if not pages:
            tk.messagebox.showerror("错误", "无法获取文件页面信息")
            return

        # 确定要处理的页面范围，加强边界检查
        start_page = max(1, min(config.get("start_page", 1), len(pages)))
        end_page = max(start_page, min(config.get("end_page", len(pages)), len(pages)))

        try:
            processing_pages = pages[start_page - 1 : end_page]
            if not processing_pages:
                tk.messagebox.showerror(
                    "错误", f"页面范围 {start_page}-{end_page} 无效或为空"
                )
                return
        except IndexError as e:
            tk.messagebox.showerror("错误", f"页面范围错误: {str(e)}")
            return

        # 开始处理
        self._process_pages(processing_pages, config, file_path)

    def _process_pages(self, pages: list, config: dict, original_file_path: str):
        """处理页面"""
        import threading

        def _process_thread():
            try:
                mode = "document"
                start_page = config.get("start_page", 1)
                total_pages = len(pages)
                results = {}

                self.right_panel.add_log(
                    "INFO", f"开始处理 {total_pages} 页，模式: {mode}"
                )

                # 使用并发处理替代垃圾的串行循环
                self._process_pages_concurrent(pages, mode, start_page, results, config)

                # 处理完成，更新UI - 使用线程安全的方式
                if results:
                    self._schedule_ui_update(self.center_panel.show_results, results)
                    self.right_panel.add_log(
                        "INFO", f"处理完成，共成功 {len(results)} 页"
                    )

                    # 检查是否有标记PDF并传递给左侧面板
                    self._handle_marked_pdf_from_results(results)
                else:
                    self._schedule_ui_update(
                        self.center_panel.show_placeholder,
                        "处理失败",
                        "没有成功处理的页面",
                    )
                    self.right_panel.add_log("ERROR", "处理失败，没有成功的页面")

                # 标记处理完成
                success = len(results) > 0
                self._schedule_ui_update(self.right_panel.processing_completed, success)

            except Exception as e:
                error_msg = str(e)  # 捕获错误消息到局部变量
                self.right_panel.add_log("ERROR", f"处理过程发生异常: {error_msg}")
                self._schedule_ui_update(self.right_panel.processing_completed, False)
                self._schedule_ui_update(
                    self.center_panel.show_placeholder,
                    "处理失败",
                    f"发生异常: {error_msg}",
                )

        # 在后台线程中处理
        threading.Thread(target=_process_thread, daemon=True).start()

    def _process_single_page(
        self, page_index: int, page: dict, mode: str, start_page: int
    ) -> tuple:
        """处理单页OCR，每个线程独立处理一页"""
        current_page = start_page + page_index
        temp_file_created = False
        page_file_path = None

        try:
            # 获取页面文件路径或创建临时文件
            page_file_path = page.get("file_path")

            if not page_file_path:
                # 如果没有文件路径（PDF页面在内存中），创建临时文件
                page_image = page.get("image")
                if page_image:
                    from src.utils.file_utils import create_temp_image

                    page_file_path = create_temp_image(
                        page_image, f"ocr_page_{current_page}"
                    )
                    temp_file_created = True
                    self.right_panel.add_log(
                        "INFO", f"为第 {current_page} 页创建临时文件"
                    )
                else:
                    return current_page, None, f"第 {current_page} 页无图像数据"

            # 执行OCR处理
            result = self._execute_ocr_request(page_file_path, mode)

            if result.get("success", False):
                page_result = self._format_ocr_result(result, mode)
                return current_page, page_result, None
            else:
                error_msg = result.get("message", "未知错误")
                return current_page, None, f"处理失败: {error_msg}"

        except Exception as e:
            return current_page, None, f"处理异常: {str(e)}"
        finally:
            # 清理为OCR处理创建的临时文件
            if temp_file_created and page_file_path and os.path.exists(page_file_path):
                try:
                    os.remove(page_file_path)
                except OSError:
                    pass  # 清理失败不影响主流程

    def _execute_ocr_request(self, page_file_path: str, mode: str):
        """执行OCR请求"""
        if mode == "text":
            return self.ocr_client.extract_text(page_file_path)
        elif mode == "formula":
            return self.ocr_client.extract_formula(page_file_path)
        elif mode == "table":
            return self.ocr_client.extract_table(page_file_path)
        elif mode == "document":
            return self.ocr_client.parse_document(page_file_path, use_markdown=True)
        else:
            return self.ocr_client.extract_text(page_file_path)

    def _format_ocr_result(self, result: dict, mode: str) -> dict:
        """格式化OCR结果"""
        if mode == "document":
            # Document模式优先使用从zip解压得到的markdown内容
            content = result.get("downloaded_content", "")
            if not content:
                # 如果没有zip内容，回退到直接返回的content
                content = result.get("content", "")
            if not content:
                content = result.get("message", "Markdown内容获取失败")
            task_type = "document"
            format_type = "markdown"
        else:
            content = result.get("content", "")
            task_type = result.get("task_type", "text")

            # 根据任务类型确定格式
            if task_type == "formula":
                format_type = "latex"
            elif task_type == "table":
                format_type = "html"
            else:
                format_type = "markdown"

        formatted_result = {"content": content, "format": format_type}

        # 添加标记PDF路径（如果有）
        marked_pdf_path = result.get("marked_pdf_path")
        if marked_pdf_path:
            formatted_result["marked_pdf_path"] = marked_pdf_path

        return formatted_result

    def _process_pages_concurrent(
        self, pages: list, mode: str, start_page: int, results: dict, config: dict
    ):
        """使用多线程并发处理OCR请求"""
        total_pages = len(pages)
        processed_count = 0

        # 智能并发控制：基于系统能力和工作负载动态调整
        max_workers = self._calculate_optimal_workers(total_pages, "ocr_processing")
        self.right_panel.add_log(
            "INFO", f"使用 {max_workers} 个并发线程处理 {total_pages} 页任务"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有页面处理任务
            future_to_page = {
                executor.submit(self._process_single_page, i, page, mode, start_page): (
                    i,
                    start_page + i,
                )
                for i, page in enumerate(pages)
            }

            for future in as_completed(future_to_page):
                try:
                    page_index, current_page = future_to_page[future]
                    current_page_num, page_result, error_msg = future.result()

                    processed_count += 1
                    progress = processed_count / total_pages

                    # 线程安全的进度更新 - 使用偏函数避免变量捕获问题
                    self._schedule_progress_update(
                        progress, processed_count, total_pages
                    )

                    if page_result:
                        # 线程安全地更新结果字典
                        with self.results_lock:
                            results[current_page_num] = page_result
                        self.right_panel.add_log(
                            "INFO", f"第 {current_page_num} 页处理成功"
                        )
                    else:
                        self.right_panel.add_log(
                            "ERROR", f"第 {current_page_num} 页{error_msg}"
                        )

                except Exception as e:
                    try:
                        page_index, current_page = future_to_page[future]
                        # 保留完整错误信息用于调试，同时提供简短摘要用于显示
                        full_error = str(e)
                        error_summary = full_error.split("\n")[0]  # 取第一行作为摘要
                        if len(error_summary) > 150:
                            error_summary = error_summary[:147] + "..."

                        self.right_panel.add_log(
                            "ERROR",
                            f"第 {current_page} 页处理异常: {error_summary}",
                            full_error,
                        )
                    except Exception as log_error:
                        # 如果连日志记录都失败，至少记录到控制台
                        print(
                            f"Critical error in page processing and logging: {log_error}"
                        )
                    finally:
                        processed_count += 1

    def _handle_marked_pdf_from_results(self, results: dict):
        """处理结果中的标记PDF并传递给左侧面板"""
        # 查找第一个包含标记PDF路径的结果
        marked_pdf_path = None
        for page_num, page_result in results.items():
            if "marked_pdf_path" in page_result:
                marked_pdf_path = page_result["marked_pdf_path"]
                break

        if marked_pdf_path:
            # 获取实际处理的页码列表
            processed_pages = list(results.keys())
            self.right_panel.add_log("INFO", f"发现标记PDF，正在加载到左侧面板...")
            # 在主线程中调用左侧面板的加载方法，传递页码映射信息
            self._schedule_ui_update(
                self.left_panel.load_marked_pdf, marked_pdf_path, processed_pages
            )
        else:
            self.right_panel.add_log("INFO", "本次处理未返回标记PDF")

    def on_closing(self):
        """窗口关闭事件"""
        # 清理左侧面板的临时文件
        if hasattr(self.left_panel, "cleanup_temp_files"):
            self.left_panel.cleanup_temp_files()

        # 保存窗口尺寸
        geometry = self.geometry()
        width, height = geometry.split("x")
        height = height.split("+")[0]
        self.settings.set("ui.window_width", int(width))
        self.settings.set("ui.window_height", int(height))

        # 保存面板分割条位置
        self._save_panel_positions()

        # 关闭窗口
        self.destroy()

    def _save_panel_positions(self):
        """保存面板分割条位置（所有三个面板）"""
        try:
            # 保存两个分割条的位置
            sash_positions = []
            for i in range(2):  # 三个面板有两个分割条
                sash_coord = self.main_paned.sash_coord(i)
                if sash_coord:
                    sash_positions.append(sash_coord[0])

            if len(sash_positions) == 2:
                self.settings.set("ui.sash_positions", sash_positions)

        except Exception as e:
            # 保存失败不影响关闭
            pass

    def _perform_startup_checks(self):
        """执行启动时的系统和API检查"""
        try:
            # 1. 系统能力验证
            validation_result = settings.validate_system_capabilities()
            if validation_result["warnings"]:
                print("系统能力检查警告:")
                for warning in validation_result["warnings"]:
                    print(f"  - {warning}")

                # 自动应用推荐配置
                if validation_result["recommendations"]:
                    changes = settings.apply_system_recommendations(validation_result)
                    if changes:
                        print("已应用系统推荐配置:")
                        for change in changes:
                            print(f"  - {change}")

            # 2. API检查
            api_url = settings.get("api.base_url", "").strip()
            if not api_url:
                self._show_api_config_dialog()
            else:
                self._perform_background_health_check()

        except Exception as e:
            print(f"启动检查失败，使用默认配置继续: {str(e)}")
            # 即使检查失败，也要继续API检查
            try:
                api_url = settings.get("api.base_url", "").strip()
                if not api_url:
                    self._show_api_config_dialog()
                else:
                    self._perform_background_health_check()
            except Exception:
                pass  # 静默处理启动失败

    def _preload_fonts(self):
        """预加载字体以避免首次渲染时的阻塞"""
        try:
            from .fonts.font_manager import font_manager

            font_manager.preload_fonts_async()
            log.info("字体预加载已启动")
        except Exception as e:
            log.warning(f"字体预加载启动失败: {e}")

    def _show_api_config_dialog(self):
        """显示API配置对话框"""
        dialog = ApiConfigDialog(self, on_configured=self._on_api_configured)
        dialog.wait_window()  # Wait for dialog to close

    def _on_api_configured(self, api_url: str):
        """API配置完成回调"""
        # 刷新右侧面板API显示
        if hasattr(self.right_panel, "refresh_api_section"):
            self.right_panel.refresh_api_section()

        # 配置完成后执行健康检查
        self._perform_background_health_check()

    def _perform_background_health_check(self):
        """后台执行API健康检查"""

        def _health_check_thread():
            try:
                result = self.ocr_client.health_check()
                message = result.get("data", {}).get(
                    "message", "API service is healthy"
                )
                self._schedule_ui_update(self._on_health_check_success, message)
            except APIError as e:
                error_msg = str(e)
                self._schedule_ui_update(self._on_health_check_failure, error_msg)
            except Exception as e:
                # 处理其他类型的错误（网络连接、超时等）
                error_msg = f"连接测试失败: {str(e)}"
                self._schedule_ui_update(self._on_health_check_failure, error_msg)

        # 更新右侧面板状态为检查中
        if hasattr(self.right_panel, "update_api_status"):
            self.right_panel.update_api_status("testing", "正在检查API连接...")

        threading.Thread(target=_health_check_thread, daemon=True).start()

    def _on_health_check_success(self, message: str):
        """健康检查成功回调"""
        if hasattr(self.right_panel, "update_api_status"):
            self.right_panel.update_api_status("healthy", "API连接正常")

    def _on_health_check_failure(self, error_msg: str):
        """健康检查失败回调"""
        if hasattr(self.right_panel, "update_api_status"):
            short_msg = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg
            self.right_panel.update_api_status("error", f"API连接失败: {short_msg}")

        # 可选：显示提示信息
        # tk.messagebox.showwarning("API Warning", f"API health check failed: {short_msg}")

    def run(self):
        """运行应用程序"""
        self.mainloop()
