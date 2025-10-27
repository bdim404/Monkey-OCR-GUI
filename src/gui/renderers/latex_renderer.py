"""Enhanced LaTeX renderer with support for multi-segment documents"""

import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext
from PIL import Image
import io
import re
import os
from typing import List, Tuple, Optional, Dict, Any
import hashlib
import tempfile
from pathlib import Path

# Import matplotlib components with fallback
try:
    import matplotlib.pyplot as plt
    import matplotlib.mathtext as mathtext
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class LaTeXRenderer:
    """Enhanced LaTeX renderer supporting multi-segment documents"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize LaTeX renderer with caching support"""
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "monkey_ocr_latex_cache")
        self._ensure_cache_dir()
        self.cached_images = {}  # Hash -> PIL Image cache
        
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        try:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        except Exception:
            # Fallback to temp directory if cache creation fails
            self.cache_dir = tempfile.gettempdir()
    
    def _get_content_hash(self, content: str, theme_mode: str = "light") -> str:
        """Generate hash for content to use as cache key"""
        combined = f"{content}_{theme_mode}_{plt.rcParams['font.size']}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def parse_latex_segments(self, latex_content: str) -> List[Dict[str, Any]]:
        """Parse LaTeX content into renderable segments"""
        segments = []
        
        # Split content by common LaTeX environments and text blocks
        patterns = [
            (r'\\begin\{equation\}(.*?)\\end\{equation\}', 'equation'),
            (r'\\begin\{align\}(.*?)\\end\{align\}', 'align'),
            (r'\\begin\{matrix\}(.*?)\\end\{matrix\}', 'matrix'),
            (r'\\begin\{array\}(.*?)\\end\{array\}', 'array'),
            (r'\$\$(.*?)\$\$', 'display_math'),
            (r'\$(.*?)\$', 'inline_math'),
            (r'\\section\{([^}]+)\}', 'section'),
            (r'\\subsection\{([^}]+)\}', 'subsection'),
            (r'\\textbf\{([^}]+)\}', 'bold'),
            (r'\\textit\{([^}]+)\}', 'italic'),
        ]
        
        remaining_content = latex_content
        position = 0
        
        while remaining_content and position < len(latex_content):
            found_match = False
            earliest_match = None
            earliest_pos = len(remaining_content)
            
            # Find the earliest pattern match
            for pattern, segment_type in patterns:
                match = re.search(pattern, remaining_content, re.DOTALL)
                if match and match.start() < earliest_pos:
                    earliest_pos = match.start()
                    earliest_match = (match, segment_type)
                    found_match = True
            
            if found_match:
                match, segment_type = earliest_match
                
                # Add text before the match as plain text
                if match.start() > 0:
                    text_content = remaining_content[:match.start()].strip()
                    if text_content:
                        segments.append({
                            'type': 'text',
                            'content': text_content,
                            'original': text_content
                        })
                
                # Add the matched segment
                segments.append({
                    'type': segment_type,
                    'content': match.group(1).strip() if match.groups() else match.group(0).strip(),
                    'original': match.group(0)
                })
                
                # Update remaining content
                remaining_content = remaining_content[match.end():]
                position += match.end()
            else:
                # No more patterns found, add remaining as text
                remaining_text = remaining_content.strip()
                if remaining_text:
                    segments.append({
                        'type': 'text',
                        'content': remaining_text,
                        'original': remaining_text
                    })
                break
        
        return segments if segments else [{'type': 'text', 'content': latex_content, 'original': latex_content}]
    
    def render_math_segment(self, content: str, theme_mode: str = "light") -> Optional[Image.Image]:
        """Render a single math segment using matplotlib"""
        if not MATPLOTLIB_AVAILABLE:
            return None
            
        try:
            # Check cache first
            cache_key = self._get_content_hash(content, theme_mode)
            if cache_key in self.cached_images:
                return self.cached_images[cache_key]
            
            # Create figure for rendering
            fig, ax = plt.subplots(figsize=(8, 2), dpi=150)
            fig.patch.set_alpha(0)  # Transparent background
            ax.patch.set_alpha(0)
            
            # Set text color based on theme
            text_color = '#e0e0e0' if theme_mode == 'dark' else '#333333'
            
            # Prepare math string for matplotlib
            if not content.startswith('$'):
                math_string = f"${content}$"
            else:
                math_string = content
            
            # Render the math
            ax.text(0.05, 0.5, 
                   math_string,
                   transform=ax.transAxes,
                   fontsize=16,
                   color=text_color,
                   verticalalignment='center',
                   horizontalalignment='left',
                   usetex=False)  # Use mathtext instead of TeX
            
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            # Save to memory buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', 
                       pad_inches=0.1, transparent=True, dpi=150)
            buf.seek(0)
            plt.close(fig)
            
            # Create PIL image
            pil_image = Image.open(buf)
            
            # Cache the image
            self.cached_images[cache_key] = pil_image
            
            return pil_image
            
        except Exception as e:
            print(f"LaTeX render error: {e}")
            return None
    
    def create_segment_widget(self, parent: tk.Widget, segment: Dict[str, Any], theme_mode: str = "light") -> tk.Widget:
        """Create appropriate widget for a LaTeX segment"""
        segment_type = segment['type']
        content = segment['content']
        
        if segment_type == 'text':
            # Plain text label
            text_color = '#e0e0e0' if theme_mode == 'dark' else '#333333'
            label = tk.Label(
                parent,
                text=content,
                font=('Arial', 12),
                fg=text_color,
                bg='transparent' if hasattr(parent, 'configure') else None,
                wraplength=parent.winfo_width() - 40 if parent.winfo_width() > 40 else 400,
                justify='left'
            )
            return label
            
        elif segment_type in ['section', 'subsection']:
            # Section headers
            text_color = '#ffffff' if theme_mode == 'dark' else '#1a1a1a'
            size = 16 if segment_type == 'section' else 14
            weight = 'bold'
            
            label = tk.Label(
                parent,
                text=content,
                font=('Arial', size, weight),
                fg=text_color,
                bg='transparent' if hasattr(parent, 'configure') else None,
                justify='left'
            )
            return label
            
        elif segment_type in ['bold', 'italic']:
            # Text formatting
            text_color = '#e0e0e0' if theme_mode == 'dark' else '#333333'
            style = 'bold' if segment_type == 'bold' else 'italic'
            
            label = tk.Label(
                parent,
                text=content,
                font=('Arial', 12, style),
                fg=text_color,
                bg='transparent' if hasattr(parent, 'configure') else None,
                justify='left'
            )
            return label
            
        else:
            # Math content - render as image
            image = self.render_math_segment(content, theme_mode)
            if image:
                try:
                    # Convert PIL image to CTkImage for display
                    ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                    label = ctk.CTkLabel(parent, image=ctk_image, text="")
                    return label
                except Exception:
                    # Fallback to text if image display fails
                    label = tk.Label(
                        parent,
                        text=f"Math: {content}",
                        font=('Courier', 10),
                        fg='#888888',
                        bg='transparent' if hasattr(parent, 'configure') else None
                    )
                    return label
            else:
                # Fallback for failed math rendering
                label = tk.Label(
                    parent,
                    text=f"Error rendering: {content}",
                    font=('Courier', 10),
                    fg='red',
                    bg='transparent' if hasattr(parent, 'configure') else None
                )
                return label
    
    def create_scrollable_view(self, parent: tk.Widget, latex_content: str, theme_mode: str = "light") -> tk.Widget:
        """Create a scrollable view for multi-segment LaTeX content"""
        if not MATPLOTLIB_AVAILABLE:
            # Fallback to text display if matplotlib is not available
            error_label = tk.Label(
                parent,
                text="LaTeX 渲染需要 matplotlib 库\n请运行: pip install matplotlib",
                font=('Arial', 12),
                fg='red',
                wraplength=400
            )
            return error_label
        
        # Create main container with scrollbar
        container = tk.Frame(parent)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        # Configure scrolling
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Parse and render segments
        segments = self.parse_latex_segments(latex_content)
        
        for i, segment in enumerate(segments):
            try:
                widget = self.create_segment_widget(scrollable_frame, segment, theme_mode)
                if widget:
                    widget.pack(pady=5, padx=10, fill='x', anchor='w')
            except Exception as e:
                # Error widget for failed segments
                error_label = tk.Label(
                    scrollable_frame,
                    text=f"Segment {i+1} error: {str(e)}",
                    font=('Arial', 10),
                    fg='red',
                    wraplength=400
                )
                error_label.pack(pady=2, padx=10, fill='x', anchor='w')
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        return container
    
    def clear_cache(self):
        """Clear the image cache"""
        self.cached_images.clear()
        
        # Also try to clear disk cache if it exists
        try:
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir, ignore_errors=True)
                self._ensure_cache_dir()
        except Exception:
            pass  # Ignore cache cleanup errors