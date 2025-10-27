"""
增强的Markdown渲染器
支持LaTeX数学公式、技术文档格式等
"""

import re
import markdown2
from typing import Dict, List, Tuple, Any
from ..styles.content_styles import ContentStyles


class EnhancedMarkdownRenderer:
    """增强的Markdown渲染器，支持LaTeX公式和技术文档特性"""
    
    def __init__(self):
        self.math_placeholders = {}
        self.math_counter = 0
    
    def render_to_html(self, markdown_content: str, theme_mode: str = "light") -> str:
        """将Markdown转换为增强的HTML，支持LaTeX公式"""
        
        # Step 1: Extract and placeholder LaTeX math
        processed_content = self._extract_math(markdown_content)
        
        # Step 2: Convert markdown to HTML
        html_content = markdown2.markdown(
            processed_content,
            extras=[
                'fenced-code-blocks', 
                'tables', 
                'break-on-newline',
                'code-friendly',
                'header-ids',
                'footnotes',
                'strike'
            ]
        )
        
        # Step 3: Restore math with proper rendering
        html_content = self._restore_math(html_content, theme_mode)
        
        # Step 4: Enhance technical document formatting
        html_content = self._enhance_technical_formatting(html_content, theme_mode)
        
        # Step 5: Create complete HTML document
        return ContentStyles.create_complete_html_document(
            html_content,
            title="Technical Document",
            theme_mode=theme_mode
        )
    
    def _extract_math(self, content: str) -> str:
        """提取LaTeX数学公式并用占位符替换"""
        self.math_placeholders = {}
        self.math_counter = 0
        
        # Pattern for display math ($$...$$)
        def replace_display_math(match):
            math_content = match.group(1)
            placeholder = f"__DISPLAY_MATH_{self.math_counter}__"
            self.math_placeholders[placeholder] = {
                'type': 'display',
                'content': math_content.strip()
            }
            self.math_counter += 1
            return placeholder
        
        # Pattern for inline math ($...$)
        def replace_inline_math(match):
            math_content = match.group(1)
            placeholder = f"__INLINE_MATH_{self.math_counter}__"
            self.math_placeholders[placeholder] = {
                'type': 'inline',
                'content': math_content.strip()
            }
            self.math_counter += 1
            return placeholder
        
        # First extract display math ($$...$$)
        content = re.sub(r'\$\$([^$]+?)\$\$', replace_display_math, content, flags=re.DOTALL)
        
        # Then extract inline math ($...$), but avoid double dollar signs
        content = re.sub(r'(?<!\$)\$([^$\n]+?)\$(?!\$)', replace_inline_math, content)
        
        return content
    
    def _restore_math(self, html_content: str, theme_mode: str) -> str:
        """恢复LaTeX数学公式为渲染后的HTML"""
        
        for placeholder, math_data in self.math_placeholders.items():
            math_type = math_data['type']
            math_content = math_data['content']
            
            if math_type == 'display':
                # Display math - use block formula styling
                math_html = self._render_display_math(math_content, theme_mode)
            else:
                # Inline math - use inline formula styling
                math_html = self._render_inline_math(math_content, theme_mode)
            
            html_content = html_content.replace(placeholder, math_html)
        
        return html_content
    
    def _render_display_math(self, math_content: str, theme_mode: str) -> str:
        """渲染显示公式"""
        colors = ContentStyles.get_theme_colors(theme_mode)
        
        # Create a styled math block
        return f'''
        <div class="math-display" style="
            margin: 20px 0;
            padding: 15px;
            background-color: {colors['code_bg']};
            border-left: 4px solid {colors['accent']};
            border-radius: 6px;
            text-align: center;
            font-family: 'Times New Roman', serif;
            font-size: 18px;
            color: {colors['text']};
        ">
            <span class="math-content" title="LaTeX: {math_content}">
                {self._convert_latex_to_unicode(math_content)}
            </span>
        </div>
        '''
    
    def _render_inline_math(self, math_content: str, theme_mode: str) -> str:
        """渲染行内公式"""
        colors = ContentStyles.get_theme_colors(theme_mode)
        
        return f'''<span class="math-inline" style="
            background-color: {colors['code_bg']};
            color: {colors['code']};
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Times New Roman', serif;
            font-style: italic;
            font-weight: normal;
        " title="LaTeX: {math_content}">
            {self._convert_latex_to_unicode(math_content)}
        </span>'''
    
    def _convert_latex_to_unicode(self, latex_content: str) -> str:
        """将LaTeX公式转换为Unicode近似表示"""
        
        # Common LaTeX symbols to Unicode mapping
        latex_unicode_map = {
            # Greek letters
            r'\\alpha': 'α', r'\\beta': 'β', r'\\gamma': 'γ', r'\\delta': 'δ',
            r'\\epsilon': 'ε', r'\\zeta': 'ζ', r'\\eta': 'η', r'\\theta': 'θ',
            r'\\iota': 'ι', r'\\kappa': 'κ', r'\\lambda': 'λ', r'\\mu': 'μ',
            r'\\nu': 'ν', r'\\xi': 'ξ', r'\\pi': 'π', r'\\rho': 'ρ',
            r'\\sigma': 'σ', r'\\tau': 'τ', r'\\upsilon': 'υ', r'\\phi': 'φ',
            r'\\chi': 'χ', r'\\psi': 'ψ', r'\\omega': 'ω',
            
            # Capital Greek letters
            r'\\Gamma': 'Γ', r'\\Delta': 'Δ', r'\\Theta': 'Θ', r'\\Lambda': 'Λ',
            r'\\Xi': 'Ξ', r'\\Pi': 'Π', r'\\Sigma': 'Σ', r'\\Phi': 'Φ',
            r'\\Psi': 'Ψ', r'\\Omega': 'Ω',
            
            # Mathematical operators
            r'\\times': '×', r'\\div': '÷', r'\\pm': '±', r'\\mp': '∓',
            r'\\cdot': '·', r'\\star': '★', r'\\circ': '∘',
            
            # Relations
            r'\\leq': '≤', r'\\geq': '≥', r'\\neq': '≠', r'\\approx': '≈',
            r'\\equiv': '≡', r'\\sim': '∼', r'\\propto': '∝',
            
            # Set theory
            r'\\in': '∈', r'\\notin': '∉', r'\\subset': '⊂', r'\\supset': '⊃',
            r'\\subseteq': '⊆', r'\\supseteq': '⊇', r'\\cup': '∪', r'\\cap': '∩',
            r'\\emptyset': '∅', r'\\exists': '∃', r'\\forall': '∀',
            
            # Calculus
            r'\\int': '∫', r'\\sum': '∑', r'\\prod': '∏', r'\\partial': '∂',
            r'\\nabla': '∇', r'\\infty': '∞',
            
            # Other symbols
            r'\\sqrt': '√', r'\\deg': '°', r'\\angle': '∠', r'\\parallel': '∥',
        }
        
        result = latex_content
        
        # Apply symbol replacements
        for latex_symbol, unicode_symbol in latex_unicode_map.items():
            result = re.sub(latex_symbol + r'\b', unicode_symbol, result)
        
        # Handle subscripts and superscripts
        result = self._convert_scripts(result)
        
        # Handle fractions
        result = self._convert_fractions(result)
        
        # Handle square roots
        result = self._convert_sqrt(result)
        
        # Clean up remaining LaTeX commands
        result = re.sub(r'\\[a-zA-Z]+\*?', '', result)
        result = re.sub(r'[{}]', '', result)
        
        return result.strip()
    
    def _convert_scripts(self, text: str) -> str:
        """转换上标和下标"""
        # Unicode subscript digits
        subscript_map = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
        # Unicode superscript digits  
        superscript_map = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')
        
        # Handle subscripts _{}
        def replace_subscript(match):
            content = match.group(1)
            return content.translate(subscript_map)
        
        # Handle superscripts ^{}
        def replace_superscript(match):
            content = match.group(1)
            # Common superscripts
            if content == '2':
                return '²'
            elif content == '3':
                return '³'
            elif content in '0123456789':
                return content.translate(superscript_map)
            else:
                return f"^{content}"
        
        text = re.sub(r'_\{([^}]+)\}', replace_subscript, text)
        text = re.sub(r'_([0-9a-zA-Z])', lambda m: m.group(1).translate(subscript_map), text)
        
        text = re.sub(r'\^\{([^}]+)\}', replace_superscript, text)
        text = re.sub(r'\^([0-9])', replace_superscript, text)
        
        return text
    
    def _convert_fractions(self, text: str) -> str:
        """转换分数"""
        # Simple fractions
        text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', text)
        return text
    
    def _convert_sqrt(self, text: str) -> str:
        """转换平方根"""
        text = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', text)
        return text
    
    def _enhance_technical_formatting(self, html_content: str, theme_mode: str) -> str:
        """增强技术文档格式"""
        colors = ContentStyles.get_theme_colors(theme_mode)
        
        # Enhance numbered sections (B.1.1, B.1.2, etc.)
        html_content = re.sub(
            r'<h([1-6])>([^<]*?)([A-Z]\.[\d\.]+)\s*([^<]*?)</h[1-6]>',
            lambda m: f'<h{m.group(1)}><span style="color: {colors["accent"]}; font-weight: bold;">{m.group(3)}</span> {m.group(4)}</h{m.group(1)}>',
            html_content
        )
        
        # Enhance table references (表 B.1.1)
        html_content = re.sub(
            r'(表\s*[A-Z]\.[\d\.]+)',
            f'<strong style="color: {colors["accent"]};">\\1</strong>',
            html_content
        )
        
        # Enhance technical terms with units (km/h, m, etc.)
        html_content = re.sub(
            r'\b(\d+(?:\.\d+)?)\s*(km/h|m/s|km|m|mm|°|%)\b',
            f'<span style="font-weight: bold; color: {colors["heading"]};">\\1\\2</span>',
            html_content
        )
        
        # Enhance Chinese text rendering
        html_content = self._enhance_chinese_text(html_content)
        
        return html_content
    
    def _enhance_chinese_text(self, html_content: str) -> str:
        """Add language attributes to enhance Chinese text rendering"""
        
        def has_chinese(text):
            """Check if text contains Chinese characters"""
            return bool(re.search(r'[\u4e00-\u9fff]', text))
        
        def wrap_chinese_paragraphs(match):
            """Wrap paragraphs containing Chinese with language attribute"""
            content = match.group(1)
            if has_chinese(content):
                return f'<p lang="zh" class="chinese">{content}</p>'
            else:
                return f'<p lang="en" class="english">{content}</p>'
        
        def wrap_chinese_headings(match):
            """Wrap headings containing Chinese with language attribute"""
            tag = match.group(1)
            content = match.group(2)
            if has_chinese(content):
                return f'<h{tag} lang="zh" class="chinese">{content}</h{tag}>'
            else:
                return f'<h{tag} lang="en" class="english">{content}</h{tag}>'
        
        # Apply language attributes to paragraphs
        html_content = re.sub(r'<p>([^<]*?)</p>', wrap_chinese_paragraphs, html_content)
        
        # Apply language attributes to headings
        html_content = re.sub(r'<h([1-6])>([^<]*?)</h[1-6]>', wrap_chinese_headings, html_content)
        
        return html_content


# Create global instance
enhanced_markdown = EnhancedMarkdownRenderer()