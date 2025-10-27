import io
import logging
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, List, Optional

import customtkinter as ctk
import fitz  # PyMuPDF
from PIL import Image, ImageTk, ImageEnhance

from ...utils.file_utils import pdf_to_images
from ...config.settings import settings

log = logging.getLogger(__name__)


class LeftPanel(ctk.CTkFrame):
    """左侧文件上传和渲染面板"""

    def __init__(
        self,
        parent,
        on_file_selected: Optional[Callable] = None,
        on_page_changed: Optional[Callable] = None,
    ):
        super().__init__(parent)

        self.on_file_selected = on_file_selected
        self.on_page_changed = on_page_changed
        self.current_file = None
        self.current_pages = []
        self.current_page_index = 0

        # 标记PDF相关属性
        self.marked_pages = []  # 存储标记PDF的页面
        self.show_marked = False  # 是否显示标记版本
        self.marked_pdf_path = None  # 标记PDF文件路径
        self.processed_pages = []  # 存储实际处理的页码列表

        # Zoom control attributes from settings;
        from ...config.settings import settings
        self.zoom_level = settings.get("ui.preview.default_zoom_level", 1.0)
        self.fit_to_window = settings.get("ui.preview.default_fit_to_window", True)
        self.zoom_step = settings.get("ui.preview.zoom_step", 0.1)
        self.zoom_step_fast = settings.get("ui.preview.zoom_step_fast", 0.25)
        self.min_zoom = settings.get("ui.preview.min_zoom", 0.1)
        self.max_zoom = settings.get("ui.preview.max_zoom", 10.0)
        self.trackpad_sensitivity = settings.get("ui.preview.trackpad_sensitivity", 1.5)

        # Document zoom memory - remember zoom settings per file;
        self.file_zoom_memory = {}  # filepath -> (zoom_level, fit_to_window)

        self.current_photo = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_widgets()
        self._bind_keyboard_shortcuts()

    def _create_widgets(self):
        """创建界面组件"""
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self.control_frame.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            self.control_frame,
            text="文件预览",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # 添加切换按钮
        self.toggle_frame = ctk.CTkFrame(self.control_frame)
        self.toggle_frame.grid(row=0, column=1, padx=5, pady=5, sticky="")

        self.toggle_btn = ctk.CTkButton(
            self.toggle_frame,
            text="显示标记",
            width=80,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self.toggle_view_mode,
            state="disabled"  # 初始状态为禁用
        )
        self.toggle_btn.grid(row=0, column=0, padx=5, pady=2)
        self.toggle_frame.grid_remove()  # 初始隐藏

        self.nav_frame = ctk.CTkFrame(self.control_frame)
        self.nav_frame.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        self.prev_btn = ctk.CTkButton(
            self.nav_frame, text="◀", width=30, command=self.prev_page
        )
        self.prev_btn.grid(row=0, column=0, padx=2, pady=2)

        self.page_label = ctk.CTkLabel(self.nav_frame, text="1/1")
        self.page_label.grid(row=0, column=1, padx=5, pady=2)

        self.next_btn = ctk.CTkButton(
            self.nav_frame, text="▶", width=30, command=self.next_page
        )
        self.next_btn.grid(row=0, column=2, padx=2, pady=2)

        # Enhanced zoom control components;
        self.zoom_frame = ctk.CTkFrame(self.nav_frame)
        self.zoom_frame.grid(row=0, column=3, padx=(10, 0), pady=2)

        # Flexible zoom input/dropdown combo;
        # Create zoom preset values based on min/max zoom configuration;
        zoom_values = []
        min_zoom_percent = int(self.min_zoom * 100)
        max_zoom_percent = int(self.max_zoom * 100)

        # Standard zoom presets within the valid range;
        standard_presets = [25, 33, 50, 67, 75, 90, 100, 110, 125, 150, 175, 200, 250, 300, 400, 500]
        for preset in standard_presets:
            if min_zoom_percent <= preset <= max_zoom_percent:
                zoom_values.append(f"{preset}%")

        # Add fit-to-window option;
        zoom_values.append("适应窗口")

        self.zoom_preset_menu = ctk.CTkComboBox(
            self.zoom_frame,
            values=zoom_values,
            width=85,
            command=self._on_zoom_preset_changed
        )
        self.zoom_preset_menu.grid(row=0, column=0, padx=2, pady=0)
        self.zoom_preset_menu.set("适应窗口")

        # Enable manual input by binding key events;
        self.zoom_preset_menu.bind("<Return>", self._on_zoom_manual_input)
        self.zoom_preset_menu.bind("<FocusOut>", self._on_zoom_manual_input)

        self.zoom_out_btn = ctk.CTkButton(
            self.zoom_frame, text="-", width=25, command=self.zoom_out
        )
        self.zoom_out_btn.grid(row=0, column=1, padx=1, pady=0)

        self.zoom_in_btn = ctk.CTkButton(
            self.zoom_frame, text="+", width=25, command=self.zoom_in
        )
        self.zoom_in_btn.grid(row=0, column=2, padx=1, pady=0)

        # Add reset button;
        self.reset_btn = ctk.CTkButton(
            self.zoom_frame, text="重置", width=40, command=self.reset_zoom
        )
        self.reset_btn.grid(row=0, column=3, padx=(5, 0), pady=0)

        self.nav_frame.grid_remove()

        # Remove hardcoded height constraint for responsive preview;
        self.drop_frame = ctk.CTkFrame(self)
        self.drop_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.drop_frame.grid_columnconfigure(0, weight=1)

        self._create_drop_zone()

        self.pdf_progress_bar = ctk.CTkProgressBar(self)
        self.pdf_progress_label = ctk.CTkLabel(self, text="PDF处理中...")

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.button_frame.grid_columnconfigure(1, weight=1)

        self.select_btn = ctk.CTkButton(
            self.button_frame, text="选择文件", width=80, command=self.select_file
        )
        self.select_btn.grid(row=0, column=0, padx=5, pady=5)

        self.clear_btn = ctk.CTkButton(
            self.button_frame,
            text="清除",
            width=60,
            command=self.clear_file,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray80", "gray20"),
        )
        self.clear_btn.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.clear_btn.grid_remove()

    def _create_drop_zone(self):
        """创建拖放区域"""
        self.drop_frame.grid_rowconfigure(0, weight=1)
        self.drop_zone = ctk.CTkFrame(
            self.drop_frame,
            corner_radius=15,
            border_width=2,
            border_color=("gray60", "gray40"),
            fg_color="transparent",
        )
        self.drop_zone.grid(row=0, column=0, rowspan=3, padx=20, pady=20, sticky="nsew")
        self.drop_zone.grid_columnconfigure(0, weight=1)
        self.drop_zone.grid_rowconfigure(0, weight=1)

        self.drop_label = ctk.CTkLabel(
            self.drop_zone,
            text="点击选择文件\n或拖拽文件到此处\n\n支持格式：\nPDF, PNG, JPG, JPEG",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray50"),
        )
        self.drop_label.grid(row=0, column=0, padx=20, pady=20)

        self.drop_zone.bind("<Button-1>", lambda e: self.select_file())
        self.drop_label.bind("<Button-1>", lambda e: self.select_file())

    def _bind_keyboard_shortcuts(self):
        """绑定键盘和鼠标快捷操作"""
        # Focus on main widget to capture keyboard events;
        self.focus_set()

        # Zoom keyboard shortcuts;
        self.bind("<Control-equal>", lambda e: self.zoom_in())  # Ctrl + =
        self.bind("<Control-plus>", lambda e: self.zoom_in())   # Ctrl + +
        self.bind("<Control-minus>", lambda e: self.zoom_out()) # Ctrl + -
        self.bind("<Control-0>", lambda e: self.reset_zoom())   # Ctrl + 0

        # Enhanced mouse wheel and trackpad zoom support;
        self.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)         # Ctrl + Mouse wheel / trackpad
        self.bind("<Control-Button-4>", lambda e: self.smooth_zoom(120))   # Ctrl + Mouse wheel up (Linux)
        self.bind("<Control-Button-5>", lambda e: self.smooth_zoom(-120))  # Ctrl + Mouse wheel down (Linux)

        # macOS specific trackpad gesture support;
        import sys
        if sys.platform == "darwin":
            self._bind_macos_gestures()

        # Track double-click state;
        self.last_click_time = 0
        self.double_click_threshold = 500  # milliseconds

        # Drag state management for pan functionality;
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_view_x = 0
        self.drag_start_view_y = 0
        self.drag_threshold = 5  # Minimum pixels to consider as drag vs click

    def _bind_macos_gestures(self):
        """绑定 macOS 特有的触控板手势支持"""
        try:
            # Native macOS trackpad gesture support without Ctrl modifier;
            # This enables natural pinch-to-zoom gestures on macOS trackpads;
            self.bind("<MouseWheel>", self._on_macos_trackpad_scroll)

            # Bind to the widget itself for better gesture capture;
            self.bind_all("<MouseWheel>", self._on_macos_trackpad_scroll)

            # Try to enable pinch gesture recognition if available;
            try:
                # Some macOS systems support magnify gesture events;
                self.bind("<Magnify>", self._on_macos_pinch_gesture)
                self.bind_all("<Magnify>", self._on_macos_pinch_gesture)
                log.info("macOS pinch gesture support enabled")
            except tk.TclError:
                # Fallback to enhanced mousewheel detection;
                log.info("Using enhanced trackpad detection for macOS gestures")

            log.info("macOS trackpad gesture bindings activated")

        except Exception as e:
            log.warning(f"Failed to bind macOS gestures: {e}")

    def _on_macos_trackpad_scroll(self, event):
        """处理 macOS 触控板滚动/缩放手势"""
        # Enhanced trackpad detection for macOS;
        delta = getattr(event, 'delta', 0)

        # Check if this is a zoom gesture (very small delta values typically indicate trackpad);
        if abs(delta) < 10:
            # This is likely a trackpad pinch-to-zoom gesture;
            # Scale up the sensitivity for natural zoom feel;
            zoom_delta = delta * 10
            self.smooth_zoom(zoom_delta)
            return "break"  # Prevent further event propagation

        # For larger deltas, this might be normal scrolling;
        # Let the normal scroll handlers deal with it;
        return None

    def _on_macos_pinch_gesture(self, event):
        """处理 macOS 原生捏合手势"""
        # This handles native macOS magnify/pinch gestures if supported;
        try:
            magnification = getattr(event, 'magnification', 0)
            if magnification != 0:
                # Convert magnification to zoom delta;
                # Positive magnification = zoom in, negative = zoom out;
                zoom_delta = magnification * 500  # Scale for appropriate response
                self.smooth_zoom(zoom_delta)
                log.debug(f"Pinch gesture: magnification={magnification}, zoom_delta={zoom_delta}")
                return "break"
        except Exception as e:
            log.debug(f"Pinch gesture handling error: {e}")

        return None

    def _on_ctrl_mousewheel(self, event):
        """处理 Ctrl + 鼠标滚轮/触控板缩放事件"""
        import sys

        # Handle both traditional mouse wheel and trackpad scrolling;
        delta = event.delta if hasattr(event, 'delta') else 0

        # Platform-specific trackpad detection and handling;
        if sys.platform == "darwin":
            # macOS: Enhanced trackpad support;
            if abs(delta) < 30:
                # Likely trackpad - use high sensitivity for natural feel;
                sensitivity_multiplier = self.trackpad_sensitivity * 8
                self.smooth_zoom(delta * sensitivity_multiplier)
            else:
                # Likely mouse wheel - use moderate amplification;
                self.smooth_zoom(delta * 3)
        else:
            # Windows/Linux: Traditional detection;
            if abs(delta) < 50:
                # Likely trackpad - use moderate amplification;
                self.smooth_zoom(delta * 5)
            else:
                # Likely mouse wheel - use standard control;
                self.smooth_zoom(delta)

    def _create_image_display(self):
        """创建图片显示区域，支持双向滚动预览"""
        for widget in self.drop_frame.winfo_children():
            widget.destroy()

        self.drop_frame.grid_rowconfigure(0, weight=1)
        self.drop_frame.grid_columnconfigure(0, weight=1)

        # Create custom scrollable canvas with both horizontal and vertical scrollbars;
        self.canvas_frame = ctk.CTkFrame(self.drop_frame, corner_radius=10)
        self.canvas_frame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        # Create canvas for image display;
        self.image_canvas = ctk.CTkCanvas(
            self.canvas_frame,
            bg="#212121" if ctk.get_appearance_mode() == "Dark" else "#ebebeb",
            highlightthickness=0
        )
        self.image_canvas.grid(row=0, column=0, sticky="nsew")

        # Create scrollbars;
        self.v_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="vertical", command=self.image_canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        self.h_scrollbar = ctk.CTkScrollbar(self.canvas_frame, orientation="horizontal", command=self.image_canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Configure canvas scrolling;
        self.image_canvas.configure(
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set
        )

        # Create image label inside canvas;
        self.current_image_label = ctk.CTkLabel(
            self.image_canvas,
            text="",
            corner_radius=0,
            fg_color="transparent"
        )

        # Create window on canvas for the image label;
        self.canvas_window = self.image_canvas.create_window(
            0, 0, anchor="nw", window=self.current_image_label
        )

        # Bind mouse events for zoom interactions and pan dragging;
        self.current_image_label.bind("<Button-1>", self._on_image_click)
        self.current_image_label.bind("<Double-Button-1>", self._on_image_double_click)
        self.current_image_label.bind("<ButtonPress-1>", self._on_drag_start)
        self.current_image_label.bind("<B1-Motion>", self._on_drag_motion)
        self.current_image_label.bind("<ButtonRelease-1>", self._on_drag_end)
        self.current_image_label.bind("<Enter>", self._on_mouse_enter)
        self.current_image_label.bind("<Leave>", self._on_mouse_leave)

        # Bind canvas events;
        self.image_canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind enhanced mouse wheel events (zoom + scroll);
        self._bind_enhanced_mousewheel_events()

        self.after(50, self._display_current_page)

    def _on_canvas_configure(self, event):
        """处理画布尺寸变化，更新滚动区域"""
        # Update the scroll region to encompass the current image;
        self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))

        # Center image both horizontally and vertically if it's smaller than canvas;
        canvas_width = event.width
        canvas_height = event.height

        if hasattr(self, 'current_image_label'):
            img_width = self.current_image_label.winfo_reqwidth()
            img_height = self.current_image_label.winfo_reqheight()

            # Calculate horizontal centering;
            if img_width < canvas_width:
                x_offset = (canvas_width - img_width) // 2
            else:
                x_offset = 0

            # Calculate vertical centering;
            if img_height < canvas_height:
                y_offset = (canvas_height - img_height) // 2
            else:
                y_offset = 0

            self.image_canvas.coords(self.canvas_window, x_offset, y_offset)
        else:
            self.image_canvas.coords(self.canvas_window, 0, 0)

    def _bind_enhanced_mousewheel_events(self):
        """绑定增强的鼠标滚轮事件（支持缩放和滚动）"""
        import sys

        def _on_mousewheel_vertical(event):
            """处理垂直滚动（无修饰键）"""
            delta = event.delta if hasattr(event, 'delta') else (120 if event.num == 4 else -120)

            # On macOS, check if this could be a trackpad zoom gesture;
            if sys.platform == "darwin" and abs(delta) < 15:
                # Very small delta might indicate trackpad pinch gesture;
                # Try zoom first, fallback to scroll;
                if hasattr(self, '_last_small_delta_time'):
                    import time
                    current_time = time.time()
                    if current_time - self._last_small_delta_time < 0.1:
                        # Rapid small deltas = likely trackpad zoom;
                        self.smooth_zoom(delta * 15)
                        return "break"

                self._last_small_delta_time = time.time()

            # Normal vertical scrolling;
            self.image_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        def _on_mousewheel_horizontal(event):
            """处理水平滚动（Shift + 滚轮）"""
            delta = event.delta if hasattr(event, 'delta') else (120 if event.num == 4 else -120)
            self.image_canvas.xview_scroll(int(-1 * (delta / 120)), "units")

        def _on_ctrl_mousewheel_widget(event):
            """处理 Ctrl + 滚轮缩放（在图像组件上）"""
            delta = event.delta if hasattr(event, 'delta') else (120 if event.num == 4 else -120)

            # Enhanced trackpad detection for macOS;
            if sys.platform == "darwin":
                if abs(delta) < 50:
                    # macOS trackpad - use enhanced sensitivity with adaptive scaling;
                    sensitivity_multiplier = self.trackpad_sensitivity * 6
                    self.smooth_zoom(delta * sensitivity_multiplier)
                else:
                    # macOS mouse wheel;
                    self.smooth_zoom(delta * 2)
            else:
                # Standard mouse wheel or Windows/Linux;
                self.smooth_zoom(delta)

        # Initialize trackpad gesture tracking;
        self._last_small_delta_time = 0

        # Bind mousewheel events to canvas and image label;
        for widget in [self.image_canvas, self.current_image_label]:
            # Standard scrolling (no modifiers);
            widget.bind("<MouseWheel>", _on_mousewheel_vertical)
            widget.bind("<Button-4>", lambda e: self.image_canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda e: self.image_canvas.yview_scroll(1, "units"))

            # Horizontal scrolling (Shift + wheel);
            widget.bind("<Shift-MouseWheel>", _on_mousewheel_horizontal)
            widget.bind("<Shift-Button-4>", lambda e: self.image_canvas.xview_scroll(-1, "units"))
            widget.bind("<Shift-Button-5>", lambda e: self.image_canvas.xview_scroll(1, "units"))

            # Zoom (Ctrl + wheel);
            widget.bind("<Control-MouseWheel>", _on_ctrl_mousewheel_widget)
            widget.bind("<Control-Button-4>", lambda e: self.smooth_zoom(120))
            widget.bind("<Control-Button-5>", lambda e: self.smooth_zoom(-120))

            # macOS specific: bind native trackpad events if supported;
            if sys.platform == "darwin":
                try:
                    # Try to bind macOS-specific trackpad events;
                    widget.bind("<Two-Finger-Pan>", _on_mousewheel_vertical)
                    widget.bind("<Pinch>", lambda e: self.smooth_zoom(getattr(e, 'magnification', 0) * 200))
                except tk.TclError:
                    pass  # These events might not be supported on all systems

        if len(self.current_pages) > 1:
            self.nav_frame.grid()
            self._update_nav_buttons()

        # Initialize zoom display;
        self._update_zoom_display()

        self.clear_btn.grid()

    def _display_current_page(self):
        """显示当前页面的预览"""
        # 如果没有原始页面，但有标记页面，仍然可以显示标记页面
        if not self.current_pages and not (self.show_marked and self.marked_pages):
            return

        # Dynamic container sizing based on available space;
        container_w = self.drop_frame.winfo_width()
        container_h = self.drop_frame.winfo_height()
        
        # If container not ready, calculate from parent dimensions
        if container_w <= 1 or container_h <= 1:
            parent_h = self.winfo_height()
            # Account for control frame (~60px) and button frame (~50px)
            estimated_h = max(400, parent_h - 110) if parent_h > 1 else 400
            container_w = self.winfo_width() - 20  # Account for padding
            container_h = estimated_h
            
            if container_w <= 1 or container_h <= 1:
                log.warning("Container dimensions not ready, retrying...")
                self.after(100, self._display_current_page)
                return

        # Optimized padding calculations for maximum preview area;
        vertical_padding = settings.get("ui.paddings.label_vertical", 8)  # Reduced padding for more space
        horizontal_padding = settings.get("ui.paddings.label_horizontal", 6)  # Reduced padding for more space
        available_h = container_h - vertical_padding
        available_w = container_w - horizontal_padding

        if available_h < 0:
            available_h = 0
        if available_w < 0:
            available_w = 0

        # Use full available height for current page display;
        curr_h = available_h

        def _create_resized_photo(image, target_w, target_h, is_current=True):
            """高质量图像创建函数，支持缩放级别控制"""
            if image is None or target_w <= 0 or target_h <= 0:
                return None

            try:
                # Calculate scale based on zoom mode;
                img_w, img_h = image.size

                # Calculate base scale for fit-to-window as reference;
                base_scale = min(target_w / img_w, target_h / img_h)

                if self.fit_to_window:
                    # Auto-fit mode: use the base scale to fit within available space
                    scale = base_scale
                    log.debug(f"Fit-to-window mode: using base_scale={scale:.3f} for image {img_w}x{img_h} -> target {target_w}x{target_h}")
                else:
                    # Manual zoom mode: zoom_level is relative to fit-to-window size
                    scale = self.zoom_level * base_scale
                    log.debug(f"Manual zoom mode: zoom_level={self.zoom_level:.3f} × base_scale={base_scale:.3f} = {scale:.3f} for image {img_w}x{img_h}")
                    # For manual zoom, calculate size based on the corrected scale
                    new_w, new_h = int(img_w * scale), int(img_h * scale)

                    # Ensure minimum size of 1x1 pixel to avoid zero-size images;
                    new_w = max(1, new_w)
                    new_h = max(1, new_h)

                    log.debug(f"Manual zoom: calculated new size {new_w}x{new_h} from {img_w}x{img_h} at corrected scale {scale:.3f}")

                    # Return early with unclipped dimensions for scrolling support
                    if new_w > 0 and new_h > 0:
                        # Use high-quality resampling for manual zoom
                        if scale > base_scale:
                            resample_method = Image.Resampling.LANCZOS  # Better for upscaling
                        else:
                            resample_method = Image.Resampling.LANCZOS  # Consistent high quality

                        resized_img = image.resize((new_w, new_h), resample_method)
                        photo = ImageTk.PhotoImage(resized_img)
                        return photo

                # For fit-to-window mode, clip to available space
                new_w, new_h = int(img_w * scale), int(img_h * scale)

                if new_w > 0 and new_h > 0:
                    # 使用最高质量的缩放算法
                    if scale > 1.0:
                        # 放大时使用CUBIC算法获得更好效果
                        resample_method = Image.Resampling.BICUBIC
                    else:
                        # 缩小时使用LANCZOS获得最佳质量
                        resample_method = Image.Resampling.LANCZOS

                    resized_img = image.resize((new_w, new_h), resample_method)

                    # 直接创建PhotoImage
                    photo = ImageTk.PhotoImage(resized_img)
                    return photo

            except Exception as e:
                log.error(f"Failed to create PhotoImage: {e}")

            return None

        # 根据当前显示模式选择页面数据源（支持部分页面标记）
        if self.show_marked and self.marked_pages:
            # 智能混合显示：优先显示标记版本，无标记时显示原始版本
            pages_to_display = self._create_hybrid_page_list()
        else:
            pages_to_display = self.current_pages

        curr_img = (
            pages_to_display[self.current_page_index]["image"]
            if len(pages_to_display) > self.current_page_index
            else None
        )

        # 简化的图片更新逻辑 - 只处理当前页面
        try:
            # 创建新的PhotoImage对象
            new_current_photo = _create_resized_photo(
                curr_img, available_w, curr_h, is_current=True
            )

            # 直接更新实例引用
            self.current_photo = new_current_photo

            # Configure GUI with error handling;
            try:
                if self.current_photo:
                    self.current_image_label.configure(image=self.current_photo, text="")
                    self.current_image_label.image = self.current_photo

                    # Update canvas scroll region after image is set;
                    self.current_image_label.update_idletasks()
                    if hasattr(self, 'image_canvas'):
                        self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))

                        # Update canvas window size to match image;
                        req_width = self.current_image_label.winfo_reqwidth()
                        req_height = self.current_image_label.winfo_reqheight()
                        self.image_canvas.itemconfig(self.canvas_window, width=req_width, height=req_height)
                else:
                    self.current_image_label.configure(image="", text="")
                    self.current_image_label.image = None
            except Exception as e:
                log.warning(f"Failed to configure current image label: {e}")
                self.current_image_label.configure(image="", text="")

        except Exception as e:
            log.error(f"Failed to create PhotoImage objects: {e}")
            # Fallback: clear current image;
            self.current_image_label.configure(image="", text="")
            return

        # 简化内存管理 - 让Python的垃圾回收器自动处理

    def toggle_view_mode(self):
        """切换显示模式（原始/标记）"""
        if not self.marked_pages:
            return  # 没有标记页面时不做处理

        self.show_marked = not self.show_marked

        # 更新按钮文字，显示标记页面信息
        if self.show_marked:
            self.toggle_btn.configure(text="显示原始")
            log.info("切换到标记版本显示")
        else:
            marked_info = f"({len(self.marked_pages)}/{len(self.current_pages)}页)"
            self.toggle_btn.configure(text=f"显示标记{marked_info}")
            log.info("切换到原始版本显示")

        # 重新显示当前页面
        self._display_current_page()

    def _create_hybrid_page_list(self):
        """创建混合页面列表，支持部分页面标记的场景；
        对于有标记的页面显示标记版本，无标记的页面显示原始版本；
        """
        if not self.marked_pages:
            return self.current_pages

        # 如果没有原始页面，只有标记页面，直接返回标记页面
        if not self.current_pages:
            return self.marked_pages

        # 如果标记页面数量等于原始页面数量，直接返回标记页面
        if len(self.marked_pages) == len(self.current_pages):
            return self.marked_pages

        # 创建标记页面的页码映射表
        marked_page_map = {}
        for marked_page in self.marked_pages:
            marked_page_map[marked_page["page_num"]] = marked_page

        # 部分页面标记的情况：创建混合列表
        hybrid_pages = []
        for original_page in self.current_pages:
            original_page_num = original_page["page_num"]

            # 检查该页码是否有对应的标记版本
            if original_page_num in marked_page_map:
                # 使用标记页面
                hybrid_pages.append(marked_page_map[original_page_num])
            else:
                # 使用原始页面
                hybrid_pages.append(original_page)

        return hybrid_pages

    def load_marked_pdf(self, marked_pdf_path: str, processed_pages: Optional[List] = None):
        """异步加载标记PDF文件，避免阻塞UI

        Args:
            marked_pdf_path: 标记PDF文件路径
            processed_pages: 实际处理的页码列表，用于正确映射标记页面到原始页面
        """
        try:
            if not os.path.exists(marked_pdf_path):
                log.error(f"标记PDF文件不存在: {marked_pdf_path}")
                return

            log.info(f"开始加载标记PDF: {marked_pdf_path}")
            self.marked_pdf_path = marked_pdf_path

            # 存储实际处理的页码信息
            self.processed_pages = processed_pages if processed_pages else []
            if self.processed_pages:
                log.info(f"接收到处理页码信息: {self.processed_pages}")

            # 显示加载进度
            self._show_marked_pdf_progress(True)

            # 异步加载标记PDF
            self._load_marked_pdf_async(marked_pdf_path)

        except Exception as e:
            log.error(f"加载标记PDF失败: {str(e)}")
            messagebox.showerror("错误", f"加载标记PDF失败: {str(e)}")
            self._show_marked_pdf_progress(False)

    def _show_marked_pdf_progress(self, show: bool):
        """显示/隐藏标记PDF加载进度"""
        if show:
            # 简单的进度提示，复用现有的进度条
            if hasattr(self, 'pdf_progress_label') and hasattr(self, 'pdf_progress_bar'):
                self.pdf_progress_label.configure(text="加载标记PDF中...")
                self.pdf_progress_label.grid(row=3, column=0, pady=(5, 0), sticky="ew")
                self.pdf_progress_bar.grid(row=4, column=0, padx=10, pady=(0, 5), sticky="ew")
                self.pdf_progress_bar.set(0.5)  # 显示中等进度
        else:
            if hasattr(self, 'pdf_progress_label') and hasattr(self, 'pdf_progress_bar'):
                self.pdf_progress_label.grid_remove()
                self.pdf_progress_bar.grid_remove()

    def _load_marked_pdf_async(self, marked_pdf_path: str):
        """在后台线程异步加载标记PDF"""
        def load_marked_worker():
            """在后台线程中执行标记PDF转换"""
            try:
                # 使用现有的PDF转换功能，标记PDF使用较低DPI以提高性能
                # pdf_to_images 已在文件顶部导入，避免线程内导入死锁
                log.info("准备开始PDF转换处理...")
                dpi = settings.get("processing.image_quality", 150)  # 标记PDF使用标准DPI
                log.info(f"开始转换标记PDF为图像，文件: {marked_pdf_path}, DPI: {dpi}")

                # 添加PDF文件验证
                if not os.path.exists(marked_pdf_path):
                    raise FileNotFoundError(f"标记PDF文件不存在: {marked_pdf_path}")

                marked_images = pdf_to_images(marked_pdf_path, dpi=dpi)
                log.info(f"标记PDF转换完成，获得 {len(marked_images)} 张图像")

                # 构建标记页面数据，包含实际页码映射
                marked_pages = []
                for i, image in enumerate(marked_images):
                    # 如果有页码映射信息，使用实际页码；否则按顺序编号
                    actual_page_num = self.processed_pages[i] if i < len(self.processed_pages) else i + 1
                    marked_pages.append({
                        "page_num": actual_page_num,
                        "image": image,
                        "file_path": None
                    })

                log.info(f"标记PDF加载完成，共 {len(marked_images)} 页")

                # 在主线程中更新UI
                def complete_marked_loading():
                    self.marked_pages = marked_pages

                    # 显示切换按钮并启用，显示标记页面信息
                    self.toggle_frame.grid()
                    marked_info = f"({len(marked_images)}/{len(self.current_pages)}页)"
                    self.toggle_btn.configure(state="normal", text=f"显示标记{marked_info}")

                    # 切换到标记版本显示
                    self.show_marked = True
                    self.toggle_btn.configure(text="显示原始")
                    self._display_current_page()

                    # 隐藏进度条
                    self._show_marked_pdf_progress(False)

                self.after(0, complete_marked_loading)

            except Exception as e:
                error_msg = str(e)
                log.error(f"标记PDF异步加载失败: {error_msg}", exc_info=True)
                # 在主线程中显示错误
                def show_error():
                    detailed_error = f"标记PDF处理失败: {error_msg}\n\n请检查:\n1. PDF文件是否完整\n2. 系统内存是否充足\n3. 临时文件目录权限"
                    messagebox.showerror("错误", detailed_error)
                    self._show_marked_pdf_progress(False)
                self.after(0, show_error)

        # 在新线程中执行标记PDF处理
        thread = threading.Thread(target=load_marked_worker, daemon=True)
        thread.start()

    def select_file(self):
        """选择文件"""
        file_types = [
            ("All Supported", "*.pdf *.png *.jpg *.jpeg"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.png *.jpg *.jpeg"),
            ("All files", "*.* "),
        ]

        file_path = filedialog.askopenfilename(title="选择文件", filetypes=file_types)

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        """加载文件"""
        try:
            # Save current file's zoom state before loading new file;
            self._save_zoom_memory()

            self.current_file = file_path
            self.current_page_index = 0

            # Restore zoom state for this file if previously viewed;
            self._restore_zoom_memory(file_path)

            if file_path.lower().endswith(".pdf"):
                self._show_pdf_progress(True)
                self._load_pdf_async(file_path)
            else:
                self._load_image(file_path)
                self._create_image_display()
                if self.on_file_selected:
                    self.on_file_selected(file_path, self.current_pages)

        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            self._show_pdf_progress(False)

    def _show_pdf_progress(self, show: bool):
        if show:
            self.pdf_progress_label.grid(row=3, column=0, pady=(5, 0), sticky="ew")
            self.pdf_progress_bar.grid(
                row=4, column=0, padx=10, pady=(0, 5), sticky="ew"
            )
            self.pdf_progress_bar.set(0)
        else:
            self.pdf_progress_label.grid_remove()
            self.pdf_progress_bar.grid_remove()

    def _load_pdf_async(self, file_path: str):
        """使用多线程异步加载PDF文件，消除垃圾的串行处理。"""
        
        def progress_callback(processed: int, total: int):
            """线程安全的进度更新回调"""
            def update_progress():
                progress = processed / total
                self.pdf_progress_bar.set(progress)
                self.pdf_progress_label.configure(
                    text=f"PDF处理中... {processed}/{total}"
                )
            # 在主线程中更新GUI
            self.after(0, update_progress)
        
        def load_pdf_worker():
            """在后台线程中执行PDF转换"""
            try:
                log.info(f"开始异步加载PDF: {file_path}")
                # 使用新的多线程PDF转换函数，预览使用高DPI
                dpi = settings.get("processing.preview_dpi", 300)
                images = pdf_to_images(file_path, dpi=dpi, progress_callback=progress_callback)
                
                # 构造页面数据，直接在内存中保存Image对象
                self.current_pages = []
                for i, image in enumerate(images):
                    # 消除临时文件创建，直接使用内存中的Image对象
                    self.current_pages.append({
                        "page_num": i + 1,
                        "image": image,
                        "file_path": None  # 不再创建临时文件，保持兼容性
                    })
                
                log.info(f"PDF加载完成，共处理{len(images)}页")
                
                # 在主线程中更新UI
                def complete_loading():
                    self._create_image_display()
                    if self.on_file_selected:
                        self.on_file_selected(file_path, self.current_pages)
                    self._show_pdf_progress(False)
                    
                self.after(0, complete_loading)
                
            except Exception as e:
                error_msg = str(e)
                log.error(f"PDF异步加载失败: {error_msg}")
                # 在主线程中显示错误
                def show_error():
                    messagebox.showerror("错误", f"PDF处理失败: {error_msg}")
                    self._show_pdf_progress(False)
                self.after(0, show_error)
        
        # 在新线程中执行PDF处理
        thread = threading.Thread(target=load_pdf_worker, daemon=True)
        thread.start()

    def zoom_in(self):
        """放大图像（智能步进）"""
        if self.zoom_level < self.max_zoom:
            self.fit_to_window = False
            # Use adaptive step based on current zoom level;
            step = self._get_adaptive_zoom_step()
            self.zoom_level = min(self.zoom_level + step, self.max_zoom)
            self._update_zoom_display()
            self._update_cursor_for_zoom_state()
            self._display_current_page()

    def zoom_out(self):
        """缩小图像（智能步进）"""
        if self.zoom_level > self.min_zoom:
            self.fit_to_window = False
            # Use adaptive step based on current zoom level;
            step = self._get_adaptive_zoom_step()
            self.zoom_level = max(self.zoom_level - step, self.min_zoom)
            self._update_zoom_display()
            self._update_cursor_for_zoom_state()
            self._display_current_page()

    def _get_adaptive_zoom_step(self):
        """根据当前缩放级别返回自适应步进值"""
        if self.zoom_level <= 0.5:
            return 0.05  # Fine steps for small zoom levels
        elif self.zoom_level <= 1.0:
            return 0.1   # Standard steps around 100%
        elif self.zoom_level <= 2.0:
            return 0.25  # Medium steps for moderate zoom
        else:
            return 0.5   # Larger steps for high zoom levels

    def fit_to_window_toggle(self):
        """切换适应窗口模式"""
        self.fit_to_window = not self.fit_to_window
        if self.fit_to_window:
            self.fit_btn.configure(text="手动")
            self.zoom_level = 1.0  # Reset to default when enabling auto-fit
        else:
            self.fit_btn.configure(text="适应")
        self._update_zoom_display()
        self._display_current_page()

    def reset_zoom(self):
        """重置到适应窗口模式"""
        self.fit_to_window = True
        self.zoom_level = 1.0
        self._update_zoom_display()
        self._display_current_page()

    def smooth_zoom_in(self, delta=None):
        """平滑放大（支持触控板）"""
        if self.zoom_level < self.max_zoom:
            self.fit_to_window = False
            if delta is not None:
                # Use delta for precise trackpad control;
                step = (delta / 120) * self.zoom_step * self.trackpad_sensitivity
            else:
                step = self.zoom_step / 2
            self.zoom_level = min(self.zoom_level + step, self.max_zoom)
            self._update_zoom_display()
            self._update_cursor_for_zoom_state()
            self._display_current_page()

    def smooth_zoom_out(self, delta=None):
        """平滑缩小（支持触控板）"""
        if self.zoom_level > self.min_zoom:
            self.fit_to_window = False
            if delta is not None:
                # Use delta for precise trackpad control;
                step = (delta / 120) * self.zoom_step * self.trackpad_sensitivity
            else:
                step = self.zoom_step / 2
            self.zoom_level = max(self.zoom_level - step, self.min_zoom)
            self._update_zoom_display()
            self._update_cursor_for_zoom_state()
            self._display_current_page()

    def smooth_zoom(self, delta):
        """通用平滑缩放方法（支持触控板精确控制）"""
        if self.zoom_level >= self.max_zoom and delta > 0:
            return  # Already at max zoom
        if self.zoom_level <= self.min_zoom and delta < 0:
            return  # Already at min zoom

        self.fit_to_window = False

        # Enhanced adaptive zoom step calculation;
        base_step = (delta / 120) * self.zoom_step * self.trackpad_sensitivity

        # Apply zoom-level dependent scaling for more natural feel;
        if self.zoom_level <= 0.5:
            # Fine control at low zoom levels;
            step_multiplier = 0.5
        elif self.zoom_level <= 1.0:
            # Standard control around 100%;
            step_multiplier = 1.0
        elif self.zoom_level <= 2.0:
            # Slightly faster at medium zoom;
            step_multiplier = 1.5
        else:
            # Faster control at high zoom levels;
            step_multiplier = 2.0

        step = base_step * step_multiplier

        # Ensure minimum step size for responsiveness;
        min_step = 0.01
        if abs(step) < min_step:
            step = min_step if step > 0 else -min_step

        # Apply zoom with smooth boundaries;
        new_zoom = self.zoom_level + step

        # Add boundary damping for smoother experience at limits;
        if new_zoom > self.max_zoom:
            # Soft boundary at max zoom - allow slight overshoot with spring-back;
            overshoot = new_zoom - self.max_zoom
            self.zoom_level = self.max_zoom - (overshoot * 0.1)
            self.zoom_level = max(self.zoom_level, self.max_zoom * 0.98)
        elif new_zoom < self.min_zoom:
            # Soft boundary at min zoom;
            undershoot = self.min_zoom - new_zoom
            self.zoom_level = self.min_zoom + (undershoot * 0.1)
            self.zoom_level = min(self.zoom_level, self.min_zoom * 1.02)
        else:
            self.zoom_level = new_zoom

        # Clamp to absolute bounds;
        self.zoom_level = max(self.min_zoom, min(self.zoom_level, self.max_zoom))

        log.debug(f"Smooth zoom: delta={delta}, step={step:.3f}, new_zoom={self.zoom_level:.3f}")

        self._update_zoom_display()
        self._display_current_page()

    def _on_image_click(self, event):
        """处理图像单击事件"""
        import time
        current_time = int(time.time() * 1000)

        # Only process click if we haven't been dragging;
        if hasattr(self, 'has_dragged') and self.has_dragged:
            self.has_dragged = False  # Reset drag flag
            return

        # Store click position for potential zoom centering;
        self.last_click_x = event.x
        self.last_click_y = event.y
        self.last_click_time = current_time

    def _on_image_double_click(self, event):
        """处理图像双击事件 - 智能缩放"""
        import time
        current_time = int(time.time() * 1000)

        # Smart zoom behavior based on current state;
        if self.fit_to_window:
            # If in fit mode, zoom to 200% at click point
            self.fit_to_window = False
            self.zoom_level = 2.0
        elif self.zoom_level >= 2.0:
            # If zoomed in, return to fit mode
            self.fit_to_window = True
            self.zoom_level = 1.0
        else:
            # If at 100% or less, zoom to 200%
            self.fit_to_window = False
            self.zoom_level = 2.0

        self._update_zoom_display()
        self._display_current_page()

    def _on_drag_start(self, event):
        """开始拖拽操作"""
        # Store initial position for all cases;
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.has_dragged = False

        # Only enable dragging if not in fit-to-window mode;
        if self.fit_to_window:
            return

        # Get current canvas scroll position;
        try:
            # Get current view position as fractions (0.0 to 1.0);
            x_view = self.image_canvas.canvasx(0)
            y_view = self.image_canvas.canvasy(0)

            self.drag_start_view_x = x_view
            self.drag_start_view_y = y_view

            # Don't set is_dragging yet - wait for movement threshold;
            self.is_dragging = False

            log.debug(f"Drag start prepared at ({event.x}, {event.y}), view at ({x_view}, {y_view})")

        except Exception as e:
            log.warning(f"Failed to prepare drag operation: {e}")
            self.is_dragging = False

    def _on_drag_motion(self, event):
        """处理拖拽移动"""
        # Skip if in fit-to-window mode;
        if self.fit_to_window:
            return

        # Calculate movement delta;
        delta_x = event.x - self.drag_start_x
        delta_y = event.y - self.drag_start_y
        distance = (delta_x ** 2 + delta_y ** 2) ** 0.5

        # Check if we've moved enough to start dragging;
        if not self.is_dragging and distance >= self.drag_threshold:
            self.is_dragging = True
            self.has_dragged = True
            # Change cursor to indicate dragging mode;
            self.current_image_label.configure(cursor="fleur")
            log.debug("Started dragging after threshold exceeded")

        if not self.is_dragging:
            return

        try:
            # Calculate new scroll position (inverted movement for natural feel);
            new_x = self.drag_start_view_x - delta_x
            new_y = self.drag_start_view_y - delta_y

            # Get scroll region bounds;
            scroll_region = self.image_canvas.cget("scrollregion")
            if scroll_region:
                # Parse scroll region: "x1 y1 x2 y2"
                x1, y1, x2, y2 = map(float, scroll_region.split())
                canvas_width = self.image_canvas.winfo_width()
                canvas_height = self.image_canvas.winfo_height()

                # Clamp scroll position to valid bounds;
                max_x = max(0, x2 - canvas_width)
                max_y = max(0, y2 - canvas_height)

                new_x = max(0, min(new_x, max_x))
                new_y = max(0, min(new_y, max_y))

                # Update canvas view;
                if x2 > canvas_width:  # Only scroll if content is wider than canvas
                    self.image_canvas.xview_moveto(new_x / max_x if max_x > 0 else 0)
                if y2 > canvas_height:  # Only scroll if content is taller than canvas
                    self.image_canvas.yview_moveto(new_y / max_y if max_y > 0 else 0)

                log.debug(f"Drag motion: delta=({delta_x}, {delta_y}), new_pos=({new_x}, {new_y})")

        except Exception as e:
            log.warning(f"Failed to handle drag motion: {e}")

    def _on_drag_end(self, event):
        """结束拖拽操作"""
        if self.is_dragging:
            self.is_dragging = False
            # Restore appropriate cursor based on zoom state;
            self._update_cursor_for_zoom_state()
            log.debug("Drag operation ended")

    def _on_mouse_enter(self, event):
        """鼠标进入图像区域"""
        self._update_cursor_for_zoom_state()

    def _on_mouse_leave(self, event):
        """鼠标离开图像区域"""
        if not self.is_dragging:
            self.current_image_label.configure(cursor="")

    def _update_cursor_for_zoom_state(self):
        """根据缩放状态更新光标"""
        if self.is_dragging:
            return  # Don't change cursor during drag

        if self.fit_to_window:
            # In fit-to-window mode, show normal cursor
            self.current_image_label.configure(cursor="")
        else:
            # In manual zoom mode, show hand cursor to indicate pan capability
            self.current_image_label.configure(cursor="hand1")

    def _on_zoom_preset_changed(self, value):
        """处理缩放预设改变事件"""
        if not value:  # Skip empty values;
            return

        try:
            if value == "适应窗口":
                self.fit_to_window = True
                self.zoom_level = 1.0
                log.info("Zoom mode set to fit-to-window")
            else:
                # Parse percentage value more robustly;
                try:
                    if value.endswith("%"):
                        percentage_str = value.replace("%", "").strip()
                        percentage = float(percentage_str)  # Use float for better precision
                    else:
                        percentage = float(value) * 100  # Handle decimal input like 1.5

                    self.fit_to_window = False
                    new_zoom = percentage / 100.0
                    self.zoom_level = max(self.min_zoom, min(new_zoom, self.max_zoom))
                    actual_percentage = self.zoom_level * 100.0
                    log.info(f"Zoom level set to {self.zoom_level:.2f} ({actual_percentage:.1f}%) from input: {value}")

                except (ValueError, TypeError):
                    log.warning(f"Invalid zoom preset value: {value}")
                    # Revert to current setting instead of ignoring;
                    self._update_zoom_display()
                    return

            # Update display immediately after successful zoom change;
            self._update_zoom_display()
            # Update cursor for new zoom state;
            self._update_cursor_for_zoom_state()
            # Force immediate page redisplay to ensure zoom is applied;
            if hasattr(self, 'current_pages') and self.current_pages:
                self.after_idle(self._display_current_page)
            else:
                self._display_current_page()

        except Exception as e:
            log.error(f"Error processing zoom preset change: {e}")
            self._update_zoom_display()  # Ensure display stays consistent

    def _on_zoom_manual_input(self, event):
        """处理手动缩放输入"""
        try:
            input_value = self.zoom_preset_menu.get().strip()

            if input_value == "适应窗口":
                self.fit_to_window = True
                self.zoom_level = 1.0
            elif input_value.endswith("%"):
                # Handle percentage input like "150%";
                percentage = float(input_value.replace("%", ""))
                self.fit_to_window = False
                self.zoom_level = max(self.min_zoom, min(percentage / 100.0, self.max_zoom))
            elif input_value.replace(".", "").replace("-", "").isdigit():
                # Handle decimal input like "1.5" or "2.25";
                zoom_value = float(input_value)
                self.fit_to_window = False
                self.zoom_level = max(self.min_zoom, min(zoom_value, self.max_zoom))
            else:
                # Invalid input, revert to current setting;
                self._update_zoom_display()
                return

            self._update_zoom_display()
            self._update_cursor_for_zoom_state()
            self._display_current_page()

        except ValueError:
            # Invalid input, revert to current setting;
            self._update_zoom_display()

    def _update_zoom_display(self):
        """更新缩放显示和控件状态"""
        try:
            # Update preset dropdown to match current zoom state;
            if self.fit_to_window:
                if hasattr(self, 'zoom_preset_menu'):
                    self.zoom_preset_menu.set("适应窗口")
                    log.debug("Updated zoom display to fit-to-window mode")
            else:
                # Format zoom level for display with enhanced precision;
                percentage = self.zoom_level * 100.0

                # Use appropriate decimal places for display;
                if percentage == int(percentage):
                    display_value = f"{int(percentage)}%"
                elif percentage < 100:
                    display_value = f"{percentage:.1f}%"
                else:
                    # For values >= 100%, use 1 decimal if needed, otherwise integer;
                    display_value = f"{percentage:.1f}%".replace('.0%', '%')

                if hasattr(self, 'zoom_preset_menu'):
                    # Always update the dropdown to show current zoom;
                    current_values = list(self.zoom_preset_menu.cget("values"))
                    if display_value in current_values:
                        self.zoom_preset_menu.set(display_value)
                    else:
                        # For custom zoom levels, still show the value;
                        self.zoom_preset_menu.set(display_value)

                log.debug(f"Updated zoom display to {display_value} (zoom_level={self.zoom_level:.3f})")

            # Update button states with proper logic;
            if hasattr(self, 'zoom_out_btn'):
                can_zoom_out = self.zoom_level > self.min_zoom and not self.fit_to_window
                self.zoom_out_btn.configure(state="normal" if can_zoom_out else "disabled")

            if hasattr(self, 'zoom_in_btn'):
                can_zoom_in = self.zoom_level < self.max_zoom and not self.fit_to_window
                self.zoom_in_btn.configure(state="normal" if can_zoom_in else "disabled")

        except Exception as e:
            log.error(f"Error updating zoom display: {e}")
            # Fallback: ensure dropdown shows something reasonable;
            if hasattr(self, 'zoom_preset_menu'):
                if self.fit_to_window:
                    self.zoom_preset_menu.set("适应窗口")
                else:
                    self.zoom_preset_menu.set(f"{int(self.zoom_level * 100)}%")

    def _save_zoom_memory(self):
        """保存当前文件的缩放状态"""
        if self.current_file:
            self.file_zoom_memory[self.current_file] = (self.zoom_level, self.fit_to_window)

    def _restore_zoom_memory(self, file_path: str):
        """恢复文件的缩放状态"""
        if file_path in self.file_zoom_memory:
            saved_zoom, saved_fit = self.file_zoom_memory[file_path]
            self.zoom_level = saved_zoom
            self.fit_to_window = saved_fit
            log.info(f"Restored zoom state for {file_path}: {saved_zoom*100:.0f}%, fit={saved_fit}")
        else:
            # Use default settings for new files;
            from ...config.settings import settings
            self.zoom_level = settings.get("ui.preview.default_zoom_level", 1.0)
            self.fit_to_window = settings.get("ui.preview.default_fit_to_window", True)

    def _load_image(self, file_path: str):
        """加载图片文件"""
        try:
            image = Image.open(file_path)
            self.current_pages = [
                {"page_num": 1, "image": image, "file_path": file_path}
            ]
        except Exception as e:
            raise Exception(f"图片处理失败: {str(e)}")

    def prev_page(self):
        """上一页"""
        try:
            if self.current_page_index > 0:
                self.set_current_page(self.current_page_index - 1)
        except Exception as e:
            log.error(f"Failed to navigate to previous page: {e}")
            # Try to recover by refreshing current page display;
            try:
                self._display_current_page()
            except Exception as recovery_error:
                log.error(f"Failed to recover page display: {recovery_error}")

    def next_page(self):
        """下一页"""
        try:
            if self.current_page_index < len(self.current_pages) - 1:
                self.set_current_page(self.current_page_index + 1)
        except Exception as e:
            log.error(f"Failed to navigate to next page: {e}")
            # Try to recover by refreshing current page display;
            try:
                self._display_current_page()
            except Exception as recovery_error:
                log.error(f"Failed to recover page display: {recovery_error}")

    def _update_nav_buttons(self):
        """更新导航按钮状态"""
        # 根据当前显示模式选择页面数据源
        if self.show_marked and self.marked_pages:
            pages_to_use = self._create_hybrid_page_list()
        else:
            pages_to_use = self.current_pages

        if len(pages_to_use) <= 1:
            self.nav_frame.grid_remove()
            return

        self.nav_frame.grid()
        current = self.current_page_index + 1
        total = len(pages_to_use)
        self.page_label.configure(text=f"{current}/{total}")

        self.prev_btn.configure(
            state="normal" if self.current_page_index > 0 else "disabled"
        )
        self.next_btn.configure(
            state="normal" if self.current_page_index < total - 1 else "disabled"
        )

    def set_current_page(self, page_index: int, trigger_callback: bool = True):
        """设置并跳转到指定页面预览"""
        # 根据当前显示模式选择页面数据源
        if self.show_marked and self.marked_pages:
            pages_to_use = self._create_hybrid_page_list()
        else:
            pages_to_use = self.current_pages

        if 0 <= page_index < len(pages_to_use):
            try:
                self.current_page_index = page_index
                self._display_current_page()
                self._update_nav_buttons()
                if trigger_callback and self.on_page_changed:
                    self.on_page_changed(self.current_page_index)
            except Exception as e:
                log.error(f"Failed to set current page to {page_index}: {e}")
                # Reset to a safe state;
                if self.current_page_index >= len(pages_to_use):
                    self.current_page_index = max(0, len(pages_to_use) - 1)
                # Try to update navigation buttons at least;
                try:
                    self._update_nav_buttons()
                except Exception:
                    pass

    def cleanup_temp_files(self):
        """简化的资源清理"""
        # 清理原始页面数据
        if self.current_pages:
            # 清理GUI图像引用
            self._clear_image_references()

            # 清理页面数据
            for page_data in self.current_pages:
                if 'image' in page_data and page_data['image'] is not None:
                    try:
                        if hasattr(page_data['image'], 'close'):
                            page_data['image'].close()
                    except Exception:
                        pass  # 忽略清理错误
                    finally:
                        page_data['image'] = None

        # 清理标记PDF数据
        self._cleanup_marked_pdf()

        # 简单的垃圾回收
        import gc
        gc.collect()

    def _cleanup_marked_pdf(self):
        """清理标记PDF相关数据"""
        # 清理标记页面数据
        if self.marked_pages:
            for page_data in self.marked_pages:
                if 'image' in page_data and page_data['image'] is not None:
                    try:
                        if hasattr(page_data['image'], 'close'):
                            page_data['image'].close()
                    except Exception:
                        pass  # 忽略清理错误
                    finally:
                        page_data['image'] = None

        # 清理标记PDF临时文件
        if self.marked_pdf_path and os.path.exists(self.marked_pdf_path):
            try:
                os.remove(self.marked_pdf_path)
                log.info(f"已清理标记PDF临时文件: {self.marked_pdf_path}")
            except Exception as e:
                log.warning(f"无法清理标记PDF临时文件: {e}")

        # 重置标记PDF相关属性
        self.marked_pages = []
        self.show_marked = False
        self.marked_pdf_path = None
        self.processed_pages = []
        self.toggle_btn.configure(state="disabled", text="显示标记")

    def _clear_image_references(self):
        """清理GUI组件中的图像引用"""
        # 清理PhotoImage引用
        self.current_photo = None

        # 清理GUI标签引用
        try:
            if hasattr(self, 'current_image_label') and self.current_image_label:
                self.current_image_label.configure(image="", text="")
                self.current_image_label.image = None
        except (AttributeError, tk.TclError):
            pass

        # 清理画布和滚动组件引用
        try:
            if hasattr(self, 'image_canvas'):
                self.image_canvas = None
            if hasattr(self, 'canvas_frame'):
                self.canvas_frame = None
            if hasattr(self, 'v_scrollbar'):
                self.v_scrollbar = None
            if hasattr(self, 'h_scrollbar'):
                self.h_scrollbar = None
            if hasattr(self, 'canvas_window'):
                self.canvas_window = None
        except AttributeError:
            pass

    def clear_file(self):
        """清除文件和所有面板内容"""
        # Save current file's zoom state before clearing;
        self._save_zoom_memory()

        self.cleanup_temp_files()
        self.current_file = None
        self.current_pages = []
        self.current_page_index = 0

        # Reset zoom state to default settings;
        from ...config.settings import settings
        self.zoom_level = settings.get("ui.preview.default_zoom_level", 1.0)
        self.fit_to_window = settings.get("ui.preview.default_fit_to_window", True)

        # 清理标记PDF相关数据
        self._cleanup_marked_pdf()

        self.nav_frame.grid_remove()
        self.clear_btn.grid_remove()
        self.toggle_frame.grid_remove()  # 隐藏切换按钮

        for widget in self.drop_frame.winfo_children():
            widget.destroy()
        self._create_drop_zone()

        if self.on_file_selected:
            self.on_file_selected(None, [])

    def has_file(self) -> bool:
        return self.current_file is not None

    def get_current_file(self) -> Optional[str]:
        return self.current_file

    def get_current_pages(self) -> List[dict]:
        return self.current_pages

    def get_current_page_index(self) -> int:
        return self.current_page_index

    def get_current_page_path(self) -> Optional[str]:
        if self.current_pages and 0 <= self.current_page_index < len(
            self.current_pages
        ):
            return self.current_pages[self.current_page_index].get("file_path")
        return None
