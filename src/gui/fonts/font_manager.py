"""
Custom Font Manager for OCR Results Display

Handles loading and embedding custom fonts into HTML content
with support for both development and PyInstaller environments.
"""

import os
import sys
import base64
import logging
import threading
from typing import Dict, Optional
from pathlib import Path

log = logging.getLogger(__name__)


class FontManager:
    """Manager for custom fonts with Base64 embedding support"""
    
    def __init__(self):
        self._font_cache: Dict[str, str] = {}
        self._base_path = self._get_base_path()
        self._loading_lock = threading.Lock()
        self._preload_started = False
        
    def _get_base_path(self) -> Path:
        """Get the application base path, handling PyInstaller environments"""
        if getattr(sys, 'frozen', False):
            # PyInstaller executable environment
            return Path(sys.executable).parent
        else:
            # Development environment - go up to project root
            return Path(__file__).parent.parent.parent.parent
    
    def _load_font_file(self, font_path: str) -> Optional[bytes]:
        """Load font file from disk and return bytes"""
        try:
            full_path = self._base_path / font_path
            if not full_path.exists():
                log.warning(f"Font file not found: {full_path}")
                return None
                
            with open(full_path, 'rb') as f:
                font_data = f.read()
                
            log.info(f"Loaded font: {font_path} ({len(font_data)} bytes)")
            return font_data
            
        except Exception as e:
            log.error(f"Failed to load font {font_path}: {e}")
            return None
    
    def get_font_data_uri(self, font_path: str, font_format: str = "woff2", non_blocking: bool = False) -> Optional[str]:
        """
        Convert font file to Base64 data URI for HTML embedding

        Args:
            font_path: Relative path to font file from project root
            font_format: Font format (woff2, woff, ttf, etc.)
            non_blocking: If True, return None if font not cached (避免阻塞主线程)

        Returns:
            Base64 data URI string or None if loading failed
        """
        # Check cache first
        cache_key = f"{font_path}:{font_format}"
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # 如果是非阻塞模式且字体未缓存，返回None
        if non_blocking:
            log.warning(f"Font {font_path} not cached, skipping to avoid blocking")
            return None

        # 使用锁确保线程安全
        with self._loading_lock:
            # 再次检查缓存（可能其他线程已加载）
            if cache_key in self._font_cache:
                return self._font_cache[cache_key]

            # Load font file
            font_data = self._load_font_file(font_path)
            if not font_data:
                return None

            # Convert to Base64
            try:
                log.info(f"开始转换字体为Base64: {font_path}")
                b64_data = base64.b64encode(font_data).decode('utf-8')
                data_uri = f"data:font/{font_format};base64,{b64_data}"

                # Cache the result
                self._font_cache[cache_key] = data_uri

                log.info(f"Generated data URI for {font_path} (Base64 size: {len(b64_data)})")
                return data_uri

            except Exception as e:
                log.error(f"Failed to encode font {font_path} to Base64: {e}")
                return None
    
    def generate_font_face_css(self, font_family: str, font_path: str,
                              font_format: str = "woff2",
                              font_weight: str = "normal",
                              font_style: str = "normal",
                              non_blocking: bool = False) -> str:
        """
        Generate CSS @font-face declaration for custom font

        Args:
            font_family: Name for the font family
            font_path: Relative path to font file
            font_format: Font format
            font_weight: Font weight (normal, bold, etc.)
            font_style: Font style (normal, italic, etc.)
            non_blocking: If True, avoid blocking operations

        Returns:
            CSS @font-face declaration or empty string if font unavailable
        """
        data_uri = self.get_font_data_uri(font_path, font_format, non_blocking)
        if not data_uri:
            if non_blocking:
                log.debug(f"@font-face for {font_family} skipped (non-blocking mode)")
            else:
                log.warning(f"Cannot generate @font-face for {font_family}: font not available")
            return ""
            
        css = f"""
        @font-face {{
            font-family: '{font_family}';
            src: url('{data_uri}') format('{font_format}');
            font-weight: {font_weight};
            font-style: {font_style};
            font-display: swap;
        }}"""
        
        return css.strip()
    
    def get_noto_serif_sc_css(self, non_blocking: bool = False) -> str:
        """Generate CSS for Noto Serif SC font"""
        return self.generate_font_face_css(
            font_family="Noto Serif SC",
            font_path="src/fonts/noto-serif-sc-v34-chinese-simplified_cyrillic_latin_latin-ext_vietnamese-regular.woff2",
            font_format="woff2",
            font_weight="normal",
            font_style="normal",
            non_blocking=non_blocking
        )
    
    def get_chinese_font_stack(self) -> str:
        """
        Get optimized font stack for Chinese text
        
        Returns:
            CSS font-family value with Noto Serif SC and fallbacks
        """
        font_families = [
            "'Noto Serif SC'",  # Our custom font (first priority)
            "'PingFang SC'",    # macOS Chinese
            "'Microsoft YaHei'", # Windows Chinese
            "'SimHei'",         # Windows Chinese fallback
            "'Source Han Serif'", # Adobe Chinese serif
            "'Noto Serif CJK SC'", # System fallback
            "serif"             # Generic serif fallback
        ]
        
        return ", ".join(font_families)
    
    def get_english_font_stack(self) -> str:
        """
        Get optimized font stack for English text
        
        Returns:
            CSS font-family value for English content
        """
        font_families = [
            "-apple-system",
            "BlinkMacSystemFont", 
            "'Segoe UI'",
            "'Helvetica Neue'",
            "Arial",
            "sans-serif"
        ]
        
        return ", ".join(font_families)

    def preload_fonts_async(self):
        """异步预加载字体以避免首次使用时的阻塞"""
        if self._preload_started:
            return

        self._preload_started = True

        def _preload_worker():
            """在后台线程中预加载字体"""
            try:
                log.info("开始异步预加载字体...")
                # 预加载主要的中文字体
                self.get_noto_serif_sc_css()
                log.info("字体预加载完成")
            except Exception as e:
                log.error(f"字体预加载失败: {e}")

        # 在后台线程中预加载
        threading.Thread(target=_preload_worker, daemon=True).start()

    def is_font_cached(self, font_path: str, font_format: str = "woff2") -> bool:
        """检查字体是否已缓存"""
        cache_key = f"{font_path}:{font_format}"
        return cache_key in self._font_cache


# Global font manager instance
font_manager = FontManager()