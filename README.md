# Monkey OCR GUI

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.2-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.11+-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

English | [简体中文](README.zh.md)

</div>

---

## 📖 Project Introduction

Monkey OCR GUI is a cross-platform graphical tool based on Monkey OCR API, designed to provide a clean, efficient, and user-friendly OCR interface. The tool supports text recognition, formula extraction, table parsing, and complete document recognition, with powerful features including multi-threaded concurrent processing, real-time progress tracking, result preview, and export.

### Core Features

- 🎯 **Multi-Mode Recognition**: Supports four recognition modes: text, formula (LaTeX), table (HTML), and document (Markdown)
- 📄 **Multi-Format Support**: Supports PDF, PNG, JPG, JPEG format files
- 🔄 **Page Navigation**: PDF multi-page file support with page browsing and selective processing
- ⚡ **High Performance**: Intelligent multi-threaded concurrent processing, automatically adjusts thread count based on system load
- 📊 **Real-time Progress**: Real-time progress bar and detailed log output
- 🎨 **Dual Display Mode**: Supports preview mode and source code mode switching
- 💾 **Flexible Export**: Supports single page or all pages export
- 🌐 **API Management**: Built-in API health check and connection testing
- 🎭 **Theme Switching**: Supports dark/light/system theme
- 🌍 **Internationalization**: Chinese and English interface switching support
- 📝 **Marked PDF**: Automatically loads and displays marked PDFs returned by API

## 📸 Screenshots

### Interface Overview

<div align="center">

**Light Theme**

![Light Theme Interface](picture/show-light.png)

**Dark Theme**

![Dark Theme Interface](picture/show-dark.png)

</div>

### OCR Recognition

<div align="center">

**Light Theme OCR**

![OCR Light Theme](picture/show-ocr-light.png)

**Dark Theme OCR**

![OCR Dark Theme](picture/show-ocr-dark.png)

</div>

## 🚀 Installation Guide

### System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, Linux
- **Python Version**: 3.11 or higher
- **Memory**: 4GB+ recommended
- **Disk Space**: At least 500MB available space

### Dependency Installation

1. **Clone Repository**

```bash
git clone https://github.com/yourusername/Dev-Monkey-OCR-GUI.git
cd Dev-Monkey-OCR-GUI
```

2. **Install Dependencies**

```bash
pip install -r requirements.txt
```

Main dependencies include:
- `customtkinter` - Modern GUI framework
- `PyMuPDF` - PDF processing
- `Pillow` - Image processing
- `requests` - HTTP requests
- `markdown2` - Markdown rendering
- `matplotlib` - LaTeX rendering support

3. **Run Application**

```bash
python main.py
```

## 📋 Usage Instructions

### First Launch

1. **API Configuration**
   - First launch will prompt for API address configuration
   - Enter the base URL of Monkey OCR API (e.g., `http://localhost:8000`)
   - Click "Test" button to verify connection

2. **Upload File**
   - Click "Select File" button in the left panel
   - Or drag and drop files to the upload area
   - Supported formats: PDF, PNG, JPG, JPEG

3. **Select Processing Range**
   - **Process Current Page**: Only process the currently displayed page
   - **Process All Pages**: Process all pages of the file
   - **Custom Range**: Specify in the page range input box (e.g., 1-5)

4. **Start Recognition**
   - Select recognition mode (text/formula/table/document)
   - Click "Start Processing" button
   - View real-time progress and logs in the right panel

5. **View Results**
   - Middle panel displays recognition results
   - **Preview Mode**: Rendered effect (Markdown/LaTeX/HTML)
   - **Source Mode**: Raw code content
   - Use page navigation buttons to switch between results of different pages

6. **Export Results**
   - **Export Current**: Export results of the currently viewed page
   - **Export All**: Batch export results of all recognized pages

### Recognition Mode Description

| Mode | Output Format | Use Case |
|------|---------------|----------|
| Text Recognition | Markdown | Plain text content, article paragraphs |
| Formula Extraction | LaTeX | Mathematical formulas, scientific papers |
| Table Extraction | HTML | Tabular data, statistical reports |
| Document Parsing | Markdown + Marked PDF | Complete documents, mixed content |

### Function Panels

#### Left Panel - File Management
- File upload and preview
- PDF page navigation
- Marked PDF loading and comparison

#### Middle Panel - Result Display
- Dual mode switching (preview/source)
- Page result navigation
- Content copy and export

#### Right Panel - Control Center
- API configuration and status
- Page selection control
- Processing progress tracking
- Real-time log output

## ⚙️ Configuration

### API Configuration

In the right panel "API Configuration" area:
- **API Address**: Base URL of Monkey OCR API
- **Test Button**: Verify API connection status
- **Status Indicator**: Shows current connection status (healthy/error/not tested)

### Performance Tuning

The application automatically detects system resources and optimizes concurrent performance:
- **CPU Load** > 80%: Reduce thread count by 50%
- **Available Memory** < 1GB: Reduce thread count by 50%
- **Available Memory** < 2GB: Reduce thread count by 25%

You can adjust default configuration by modifying `src/config/settings.py`:

```python
"performance": {
    "concurrency": {
        "ocr_processing": 4,
        "min_workers": 2,
        "max_workers": 16
    }
}
```

### Theme Settings

Theme switching is available at the bottom of the right panel:
- **System**: Automatically adapts to system theme
- **Dark Mode**: Dark interface
- **Light Mode**: Light interface

## 🛠️ Development Guide

### Project Structure

```
Dev-Monkey-OCR-GUI/
├── main.py                 # Application entry
├── requirements.txt        # Dependency list
├── version.json           # Version info
├── src/
│   ├── api/              # API client
│   │   └── monkey_ocr_client.py
│   ├── config/           # Configuration management
│   │   └── settings.py
│   ├── gui/              # GUI components
│   │   ├── main_window.py
│   │   ├── panels/       # Panel components
│   │   ├── dialogs/      # Dialogs
│   │   ├── renderers/    # Content renderers
│   │   └── styles/       # Style definitions
│   └── utils/            # Utility functions
│       ├── file_utils.py
│       └── i18n.py
└── locales/              # Internationalization resources
    ├── zh_CN.json
    └── en_US.json
```

### Build from Source

Package as standalone executable using PyInstaller:

```bash
pyinstaller monkey_ocr.spec
```

Generated executable is located in the `dist/` directory.

### Technical Highlights

#### 1. Intelligent Concurrency Control
- Automatically detects system CPU and memory status
- Dynamically adjusts worker thread count
- Prevents system overload

#### 2. Connection Pool Management
- HTTP connection pool reuse
- Reduces connection establishment overhead
- Improves concurrent performance

#### 3. Retry Mechanism
- Automatically retries network errors
- Exponential backoff strategy
- Maximum 3 retry attempts

#### 4. Error Handling
- Fine-grained exception classification
- Detailed error logging
- User-friendly prompts

#### 5. Resource Management
- Automatic temporary file cleanup
- Startup cleanup of expired cache
- Exit cleanup of all temporary resources

## ❓ FAQ

### Q1: What to do if API connection fails?
**A**: Check the following:
1. Confirm API service is running
2. Check if URL format is correct (e.g., `http://localhost:8000`)
3. Confirm firewall is not blocking the connection
4. Check log output for detailed error information

### Q2: Why is processing slow?
**A**: Possible reasons:
1. High network latency
2. Insufficient system resources (CPU/memory)
3. Processing large files or many pages
4. High API server load

Try:
- Reduce concurrent page count
- Process large files in batches
- Upgrade system hardware

### Q3: What file formats are supported?
**A**: Currently supported:
- **Images**: PNG, JPG, JPEG
- **Documents**: PDF (multi-page support)

### Q4: How to change interface language?
**A**: The application automatically detects system language. You can manually switch by modifying the configuration file:
```python
"ui": {
    "language": "zh_CN"  # or "en_US"
}
```

### Q5: Where are exported files saved?
**A**: A file selection dialog will pop up during export, allowing you to freely choose the save location.

### Q6: How to update to the latest version?
**A**:
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- [Monkey OCR API](https://github.com/Yuliang-Liu/MonkeyOCR) - MonkeyOCR: Document Parsing with a Structure-Recognition-Relation Triplet Paradigm 
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern Tkinter interface library
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - High-performance PDF processing library
