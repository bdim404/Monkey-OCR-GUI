# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Get the project root directory;
project_root = Path('.').resolve()

# Conditional file existence checks for optional resources;
def add_data_if_exists(src_path, dst_path):
    """Add data file to the list only if it exists;"""
    if os.path.exists(src_path):
        return [(src_path, dst_path)]
    return []

# Build data files list with existence checks;
data_files = []

# Add locales directory for internationalization support;
locales_dir = project_root / 'locales'
if locales_dir.exists():
    for locale_file in locales_dir.glob('*.json'):
        data_files.append((str(locale_file), 'locales'))

# Add config.json if it exists;
config_file = project_root / 'config.json'
data_files.extend(add_data_if_exists(str(config_file), '.'))

# Add version.json if it exists;
version_file = project_root / 'version.json'
data_files.extend(add_data_if_exists(str(version_file), '.'))

# Hidden imports for better compatibility;
hidden_imports = [
    # CustomTkinter and GUI related;
    'customtkinter',
    'customtkinter.windows',
    'customtkinter.windows.widgets',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    
    # HTML/Markdown rendering;
    'tkhtmlview',
    'markdown2',
    'pygments',
    'pygments.lexers',
    'pygments.formatters',
    
    # Image processing;
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    
    # PDF processing;
    'fitz',  # PyMuPDF;
    'pymupdf',
    
    # HTTP and networking;
    'requests',
    'urllib3',
    'tenacity',
    
    # JSON and utilities;
    'json',
    'jsbeautifier',
    'tqdm',
    
    # Application modules;
    'src',
    'src.gui',
    'src.gui.main_window',
    'src.gui.panels',
    'src.gui.panels.left_panel',
    'src.gui.panels.center_panel',
    'src.gui.panels.right_panel',
    'src.gui.panels.right_panel_sections',
    'src.gui.panels.right_panel_sections.api_section',
    'src.gui.panels.right_panel_sections.control_section',
    'src.gui.panels.right_panel_sections.log_section',
    'src.gui.panels.right_panel_sections.mode_section',
    'src.gui.panels.right_panel_sections.page_section',
    'src.gui.panels.right_panel_sections.progress_section',
    'src.config',
    'src.config.settings',
    'src.api',
    'src.api.monkey_ocr_client',
    'src.utils',
    'src.utils.file_utils',
    'src.utils.i18n',
]

# Modules to exclude from the build;
exclude_modules = [
    'matplotlib',
    'numpy',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'setuptools',
    'distutils',
]

# Check for icon file;
icon_path = None
possible_icons = ['icon.ico', 'app.ico', 'monkey.ico', 'assets/icon.ico']
for icon_file in possible_icons:
    if os.path.exists(icon_file):
        icon_path = icon_file
        break

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=exclude_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MonkeyOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application, no console window;
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,  # Will be None if no icon found;
)