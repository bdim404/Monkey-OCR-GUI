"""Enhanced content display styles with modern HTML/CSS support"""

import customtkinter as ctk
import logging
import re
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

log = logging.getLogger(__name__)

# Import our custom font manager
try:
    from ..fonts.font_manager import font_manager
    CUSTOM_FONTS_AVAILABLE = True
except ImportError:
    CUSTOM_FONTS_AVAILABLE = False


class ContentStyles:
    """Advanced HTML enhancer with full CSS support"""
    
    @staticmethod
    def get_theme_colors(theme_mode: str = None) -> dict:
        """Get comprehensive color scheme based on theme mode"""
        if theme_mode is None:
            theme_mode = ctk.get_appearance_mode().lower()
        
        if theme_mode == "dark":
            return {
                'text': '#e0e0e0',
                'heading': '#ffffff', 
                'accent': '#4a9eff',
                'code': '#f8f8f2',
                'muted': '#888888',
                'background': '#1e1e1e',
                'code_bg': '#2d2d2d',
                'table_border': '#555555',
                'table_header': '#3d3d3d',
                'highlight': '#ffd700',
                'success': '#90ee90',
                'warning': '#ffa500',
                'error': '#ff6b6b'
            }
        else:
            return {
                'text': '#333333',
                'heading': '#1a1a1a',
                'accent': '#0066cc',
                'code': '#2d3748',
                'muted': '#666666',
                'background': '#ffffff',
                'code_bg': '#f8f9fa',
                'table_border': '#dee2e6',
                'table_header': '#e9ecef',
                'highlight': '#fff3cd',
                'success': '#d4edda',
                'warning': '#fff3cd',
                'error': '#f8d7da'
            }
    
    @staticmethod
    def enhance_markdown_html(html_content: str, theme_mode: str = None) -> str:
        """Enhance markdown-generated HTML with inline styles for tkhtmlview"""
        colors = ContentStyles.get_theme_colors(theme_mode)
        
        # Enhance headings with colors and sizes;
        html_content = re.sub(
            r'<h1>(.*?)</h1>', 
            f'<h1><font color="{colors["heading"]}" size="6"><b>\\1</b></font></h1>', 
            html_content, flags=re.DOTALL
        )
        
        html_content = re.sub(
            r'<h2>(.*?)</h2>', 
            f'<h2><font color="{colors["heading"]}" size="5"><b>\\1</b></font></h2>', 
            html_content, flags=re.DOTALL
        )
        
        html_content = re.sub(
            r'<h3>(.*?)</h3>', 
            f'<h3><font color="{colors["accent"]}" size="4"><b>\\1</b></font></h3>', 
            html_content, flags=re.DOTALL
        )
        
        # Enhance code blocks with background color using basic styling;
        html_content = re.sub(
            r'<code>(.*?)</code>', 
            f'<font color="{colors["code"]}"><tt>\\1</tt></font>', 
            html_content, flags=re.DOTALL
        )
        
        # Enhance links;
        html_content = re.sub(
            r'<a href="([^"]*)">(.*?)</a>', 
            f'<a href="\\1"><font color="{colors["accent"]}"><u>\\2</u></font></a>', 
            html_content, flags=re.DOTALL
        )
        
        # Enhance strong/bold text;
        html_content = re.sub(
            r'<strong>(.*?)</strong>', 
            f'<b><font color="{colors["heading"]}">\\1</font></b>', 
            html_content, flags=re.DOTALL
        )
        
        # Enhance emphasis/italic text;
        html_content = re.sub(
            r'<em>(.*?)</em>', 
            f'<i><font color="{colors["accent"]}">\\1</font></i>', 
            html_content, flags=re.DOTALL
        )
        
        return html_content
    
    @staticmethod
    def enhance_basic_html(html_content: str, theme_mode: str = None) -> str:
        """Enhance basic HTML content with minimal inline styling"""
        colors = ContentStyles.get_theme_colors(theme_mode)
        
        # Add default text color to body if not present;
        if '<body' in html_content.lower():
            html_content = re.sub(
                r'<body([^>]*)>', 
                f'<body\\1><font color="{colors["text"]}">', 
                html_content, flags=re.IGNORECASE
            )
            html_content = html_content.replace('</body>', '</font></body>')
        else:
            # If no body tag, wrap entire content;
            html_content = f'<font color="{colors["text"]}">{html_content}</font>'
        
        return html_content
    
    @staticmethod
    def generate_modern_css(theme_mode: str = None) -> str:
        """Generate comprehensive CSS for modern HTML rendering with custom fonts"""
        colors = ContentStyles.get_theme_colors(theme_mode)
        
        # Get font stacks from font manager
        if CUSTOM_FONTS_AVAILABLE:
            chinese_fonts = font_manager.get_chinese_font_stack()
            english_fonts = font_manager.get_english_font_stack()
        else:
            chinese_fonts = "'PingFang SC', 'Microsoft YaHei', 'SimHei', serif"
            english_fonts = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
        
        # Start with custom font declarations
        font_declarations = ""
        if CUSTOM_FONTS_AVAILABLE:
            # 尝试使用缓存的字体，如果未缓存则跳过以避免阻塞
            noto_serif_css = font_manager.get_noto_serif_sc_css(non_blocking=True)
            if noto_serif_css:
                font_declarations = noto_serif_css + "\n        "
            else:
                log.debug("Noto Serif SC font not available, using system fonts")
        
        css = f"""
        <style>
        {font_declarations}
        
        body {{
            font-family: {chinese_fonts};
            line-height: 1.6;
            color: {colors['text']};
            background-color: {colors['background']};
            margin: 20px;
            font-size: 14px;
        }}
        
        /* Enhanced font rendering for different languages */
        body:lang(en), .english {{
            font-family: {english_fonts};
        }}
        
        body:lang(zh), .chinese {{
            font-family: {chinese_fonts};
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            font-family: {chinese_fonts};
            color: {colors['heading']};
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        
        h1 {{ font-size: 2em; border-bottom: 1px solid {colors['table_border']}; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid {colors['table_border']}; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}
        h4 {{ font-size: 1em; }}
        h5 {{ font-size: 0.875em; }}
        h6 {{ font-size: 0.85em; color: {colors['muted']}; }}
        
        p {{ margin-bottom: 16px; }}
        
        a {{
            color: {colors['accent']};
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        code {{
            background-color: {colors['code_bg']};
            color: {colors['code']};
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 85%;
        }}
        
        pre {{
            background-color: {colors['code_bg']};
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            line-height: 1.45;
            margin-bottom: 16px;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        
        blockquote {{
            padding: 0 16px;
            color: {colors['muted']};
            border-left: 4px solid {colors['table_border']};
            margin: 0 0 16px 0;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}
        
        table th, table td {{
            border: 1px solid {colors['table_border']};
            padding: 8px 12px;
            text-align: left;
        }}
        
        table th {{
            background-color: {colors['table_header']};
            font-weight: 600;
        }}
        
        table tr:nth-child(even) {{
            background-color: {colors['code_bg']};
        }}
        
        ul, ol {{
            margin-bottom: 16px;
            padding-left: 30px;
        }}
        
        li {{
            margin-bottom: 4px;
        }}
        
        hr {{
            border: none;
            height: 1px;
            background-color: {colors['table_border']};
            margin: 24px 0;
        }}
        
        .highlight {{
            background-color: {colors['highlight']};
            padding: 2px 4px;
            border-radius: 3px;
        }}
        
        .success {{
            background-color: {colors['success']};
            border-radius: 4px;
            padding: 8px 12px;
            margin-bottom: 16px;
        }}
        
        .warning {{
            background-color: {colors['warning']};
            border-radius: 4px;
            padding: 8px 12px;
            margin-bottom: 16px;
        }}
        
        .error {{
            background-color: {colors['error']};
            border-radius: 4px;
            padding: 8px 12px;
            margin-bottom: 16px;
        }}
        </style>
        """
        return css
    
    @staticmethod
    def add_syntax_highlighting(html_content: str) -> str:
        """Add syntax highlighting to code blocks using Pygments"""
        def highlight_code_block(match):
            # Extract language and code
            full_match = match.group(0)
            code_content = match.group(2) if match.group(2) else match.group(1)
            
            # Try to extract language from class attribute
            lang_match = re.search(r'class="language-(\w+)"', full_match)
            language = lang_match.group(1) if lang_match else None
            
            try:
                # Get lexer
                if language:
                    lexer = get_lexer_by_name(language, stripall=True)
                else:
                    lexer = guess_lexer(code_content)
                
                # Generate HTML with syntax highlighting
                formatter = HtmlFormatter(
                    style='monokai' if ctk.get_appearance_mode() == "Dark" else 'default',
                    noclasses=True,
                    nobackground=True
                )
                
                highlighted = highlight(code_content, lexer, formatter)
                
                # Wrap in pre tag if not already wrapped
                if not full_match.startswith('<pre'):
                    highlighted = f'<pre>{highlighted}</pre>'
                
                return highlighted
                
            except (ClassNotFound, ValueError):
                # Fallback to plain code block
                return f'<pre><code>{code_content}</code></pre>'
        
        # Pattern for code blocks (both <pre><code> and <code> variants)
        code_block_pattern = r'<pre[^>]*><code[^>]*>(.*?)</code></pre>|<code[^>]*>(.*?)</code>'
        
        return re.sub(code_block_pattern, highlight_code_block, html_content, flags=re.DOTALL)
    
    @staticmethod
    def create_complete_html_document(content: str, title: str = "Document", theme_mode: str = None) -> str:
        """Create a complete HTML document with enhanced styling"""
        css = ContentStyles.generate_modern_css(theme_mode)
        
        # Add syntax highlighting
        enhanced_content = ContentStyles.add_syntax_highlighting(content)
        
        # Create complete HTML document
        html_doc = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            {css}
        </head>
        <body>
            {enhanced_content}
        </body>
        </html>
        """
        
        return html_doc
    
    @staticmethod
    def add_simple_table_styling(html_content: str) -> str:
        """Add basic table styling using HTML attributes instead of CSS"""
        # Add border and cellpadding to tables;
        html_content = re.sub(
            r'<table>', 
            '<table border="1" cellpadding="4" cellspacing="0">', 
            html_content, flags=re.IGNORECASE
        )
        
        return html_content