"""
文件处理工具函数

提供PDF转换、临时文件管理、文件验证等功能。
"""

import os
import tempfile
import platform
import time
import glob
import io
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Optional, Callable
from PIL import Image

# 从配置模块导入设置
from src.config.settings import settings

# 配置日志
logging.basicConfig(level=settings.get("logging.level", "INFO"))
log = logging.getLogger(__name__)

class FileProcessingError(Exception):
    """文件处理相关异常基类"""
    pass

class RecoverableProcessingError(FileProcessingError):
    """可恢复的处理错误 - 单页失败但可继续处理"""
    def __init__(self, page_num: int, message: str, original_exception: Exception = None):
        self.page_num = page_num
        self.original_exception = original_exception
        super().__init__(f"Page {page_num + 1}: {message}")

class CriticalProcessingError(FileProcessingError):
    """严重处理错误 - 必须中断整个处理流程"""
    def __init__(self, message: str, failed_pages: List[int] = None, original_exception: Exception = None):
        self.failed_pages = failed_pages or []
        self.original_exception = original_exception
        super().__init__(message)

def _classify_error(exception: Exception, page_num: int) -> FileProcessingError:
    """分类异常类型，返回相应的处理错误对象"""
    import fitz
    
    # 内存相关错误 - 严重错误
    if isinstance(exception, MemoryError):
        return CriticalProcessingError(
            f"内存不足，无法处理大文件",
            failed_pages=[page_num],
            original_exception=exception
        )
    
    # 文件访问错误 - 严重错误
    if isinstance(exception, (PermissionError, FileNotFoundError, OSError)):
        return CriticalProcessingError(
            f"文件访问失败: {str(exception)}",
            failed_pages=[page_num],
            original_exception=exception
        )
    
    # PDF结构错误 - 可恢复错误
    if "PDF" in str(exception) or isinstance(exception, (RuntimeError, ValueError)):
        return RecoverableProcessingError(
            page_num,
            f"PDF页面结构损坏或格式不支持: {str(exception)}",
            original_exception=exception
        )
    
    # 图像处理错误 - 可恢复错误
    if "image" in str(exception).lower() or "pix" in str(exception).lower():
        return RecoverableProcessingError(
            page_num,
            f"图像处理失败: {str(exception)}",
            original_exception=exception
        )
    
    # 默认为可恢复错误
    return RecoverableProcessingError(
        page_num,
        f"页面处理异常: {str(exception)}",
        original_exception=exception
    )

# --- 临时目录管理 ---

def get_temp_dir() -> str:
    """简化的临时目录获取逻辑"""
    temp_dir_name = settings.get("cache.temp_dir_name", "monkey_ocr_temp")
    
    # 简化的尝试顺序
    try:
        # 1. 对于exe环境，尝试exe目录
        if getattr(sys, 'frozen', False):
            exe_temp_dir = os.path.join(os.path.dirname(sys.executable), temp_dir_name)
            os.makedirs(exe_temp_dir, exist_ok=True)
            return exe_temp_dir
        
        # 2. 对于开发环境，使用系统临时目录
        system_temp_dir = os.path.join(tempfile.gettempdir(), temp_dir_name)
        os.makedirs(system_temp_dir, exist_ok=True)
        return system_temp_dir
        
    except Exception as e:
        log.warning(f"临时目录创建失败，使用系统默认: {e}")
        return tempfile.gettempdir()

# --- PDF 处理 --- 

# 动态检查可用的PDF库
PYMUPDF_AVAILABLE = False
PDF2IMAGE_AVAILABLE = False
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    pass

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    pass

def pdf_to_images(pdf_path: str, dpi: int = 150, progress_callback: Optional[Callable] = None) -> List[Image.Image]:
    """将PDF转换为图片列表，使用多线程并发处理提升性能。"""
    if PYMUPDF_AVAILABLE:
        log.info("使用 PyMuPDF (fitz) 引擎进行多线程PDF转换...")
        try:
            return _pdf_to_images_with_fitz_concurrent(pdf_path, dpi, progress_callback)
        except Exception as e:
            log.warning(f"PyMuPDF 并发转换失败，尝试串行: {e}")
            try:
                return _pdf_to_images_with_fitz(pdf_path, dpi)
            except Exception as serial_e:
                log.warning(f"PyMuPDF 串行转换失败: {serial_e}")
                if PDF2IMAGE_AVAILABLE:
                    log.info("尝试使用备选引擎 pdf2image...")
                else:
                    raise Exception(f"PDF处理失败，且无备选引擎。错误: {serial_e}")

    if PDF2IMAGE_AVAILABLE:
        log.info("使用 pdf2image 引擎进行PDF转换...")
        try:
            return _pdf_to_images_with_pdf2image(pdf_path, dpi)
        except Exception as e:
            log.error(f"pdf2image 转换也失败: {e}")
            raise Exception(f"所有PDF处理引擎都失败了。错误: {e}")

    raise Exception("没有可用的PDF处理库。请安装 PyMuPDF (推荐) 或 pdf2image。")

def _pdf_to_images_with_fitz_concurrent(pdf_path: str, dpi: int, progress_callback: Optional[Callable] = None) -> List[Image.Image]:
    """使用 PyMuPDF (fitz) 多线程并发转换PDF，消除垃圾串行处理。"""
    import fitz
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    
    if total_pages == 0:
        return []
    
    log.info(f"开始并发转换PDF，共{total_pages}页")
    
    # 从配置获取线程数，智能调整
    max_workers = settings.get_worker_count("pdf_processing")
    # 根据页面数调整，避免创建过多线程
    max_workers = min(max_workers, total_pages)
    
    def process_single_page(page_num: int) -> Tuple[int, Image.Image]:
        """处理单页PDF，每个线程独立打开文档避免线程冲突。"""
        thread_doc = None
        pix = None
        try:
            # 每个线程独立打开文档，避免共享状态
            thread_doc = fitz.open(pdf_path)
            page = thread_doc[page_num]
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            image = Image.open(io.BytesIO(img_data))
            return page_num, image
        except Exception as e:
            log.error(f"处理第{page_num + 1}页失败: {e}")
            raise e
        finally:
            # 确保释放内存资源，避免内存泄漏
            if pix is not None:
                pix = None  # 释放pixmap内存
            if thread_doc is not None:
                thread_doc.close()  # 关闭文档
    
    images = [None] * total_pages
    processed_count = 0
    failed_pages = []
    critical_errors = []
    recoverable_errors = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有页面处理任务
        future_to_page = {executor.submit(process_single_page, i): i for i in range(total_pages)}
        
        for future in as_completed(future_to_page):
            try:
                page_num, image = future.result()
                images[page_num] = image
                processed_count += 1
                
                # 线程安全的进度回调
                if progress_callback:
                    progress_callback(processed_count, total_pages)
                    
            except Exception as e:
                page_num = future_to_page[future]
                classified_error = _classify_error(e, page_num)
                
                if isinstance(classified_error, CriticalProcessingError):
                    # 严重错误，记录并考虑中断
                    log.error(f"严重错误 - {classified_error}")
                    critical_errors.append(classified_error)
                    failed_pages.append(page_num)
                    
                    # 如果严重错误过多，中断处理
                    if len(critical_errors) >= 3:  # 允许最多3个严重错误
                        log.error(f"严重错误过多({len(critical_errors)}个)，中断处理")
                        # 取消剩余任务
                        for remaining_future in future_to_page:
                            remaining_future.cancel()
                        raise CriticalProcessingError(
                            f"处理中断：连续{len(critical_errors)}个严重错误",
                            failed_pages=failed_pages,
                            original_exception=e
                        )
                else:
                    # 可恢复错误，记录并继续
                    log.warning(f"页面错误 - {classified_error}")
                    recoverable_errors.append(classified_error)
                    failed_pages.append(page_num)
                
                processed_count += 1
                if progress_callback:
                    progress_callback(processed_count, total_pages)
    
    # 过滤掉失败的页面
    successful_images = [img for img in images if img is not None]
    
    # 评估处理结果
    success_count = len(successful_images)
    failure_count = len(failed_pages)
    
    if not successful_images:
        error_summary = f"所有{total_pages}页处理均失败"
        if critical_errors:
            error_summary += f"，包含{len(critical_errors)}个严重错误"
        if recoverable_errors:
            error_summary += f"，{len(recoverable_errors)}个可恢复错误"
        raise CriticalProcessingError(
            error_summary,
            failed_pages=failed_pages,
            original_exception=critical_errors[0].original_exception if critical_errors else None
        )
    
    # 记录处理结果摘要
    if failure_count > 0:
        failure_rate = (failure_count / total_pages) * 100
        log.warning(f"部分页面处理失败：{failure_count}/{total_pages}页 ({failure_rate:.1f}%)")
        
        if critical_errors:
            log.warning(f"严重错误: {[f'第{e.page_num+1}页' for e in critical_errors]}")
        if recoverable_errors:
            log.info(f"可恢复错误: {[f'第{e.page_num+1}页' for e in recoverable_errors]}")
    
    log.info(f"并发PDF转换完成，成功处理 {success_count}/{total_pages} 页")
    return successful_images

def _pdf_to_images_with_fitz(pdf_path: str, dpi: int) -> List[Image.Image]:
    """使用 PyMuPDF (fitz) 串行转换PDF，作为并发处理的降级方案"""
    images = []
    doc = None
    
    try:
        doc = fitz.open(pdf_path)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        for page in doc:
            pix = None
            try:
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("ppm")
                images.append(Image.open(io.BytesIO(img_data)))
            finally:
                # 确保释放pixmap内存
                if pix is not None:
                    pix = None
    finally:
        # 确保关闭文档
        if doc is not None:
            doc.close()
    
    return images

def _pdf_to_images_with_pdf2image(pdf_path: str, dpi: int) -> List[Image.Image]:
    """使用 pdf2image 转换PDF"""
    kwargs = {'dpi': dpi}
    if platform.system() == 'Windows':
        kwargs['poppler_path'] = _find_poppler_path()
    
    try:
        return convert_from_path(pdf_path, **kwargs)
    except Exception as e:
        if "poppler" in str(e).lower():
            raise Exception("Poppler未找到或配置错误。请确保已安装并配置好Poppler。")
        raise e

def _find_poppler_path() -> Optional[str]:
    """在Windows上查找Poppler路径"""
    # 可以在此处添加更复杂的查找逻辑，例如从注册表或环境变量
    common_paths = [
        r'C:\Program Files\poppler\bin',
        r'C:\poppler\bin',
        os.path.join(os.getcwd(), 'poppler', 'bin')
    ]
    for path in common_paths:
        if os.path.exists(path):
            log.info(f"找到Poppler路径: {path}")
            return path
    return None

# --- 文件操作 ---

def create_temp_image(image: Image.Image, prefix: str = 'page') -> str:
    """在临时目录中创建一个带时间戳的PNG图片。"""
    temp_dir = get_temp_dir()
    timestamp = int(time.time() * 1000)
    temp_path = os.path.join(temp_dir, f"{prefix}_{timestamp}.png")
    try:
        image.save(temp_path, 'PNG')
        log.info(f"创建临时图片: {temp_path}")
        return temp_path
    except IOError as e:
        log.error(f"创建临时文件失败: {e}")
        raise

def cleanup_temp_files(older_than_hours: Optional[int] = None):
    """清理临时文件。如果指定了时间，则只清理旧文件。"""
    temp_dir = get_temp_dir()
    if not os.path.exists(temp_dir):
        return

    log.info(f"开始清理临时目录: {temp_dir}")
    now = time.time()
    cleaned_count = 0
    
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(file_path):
                if older_than_hours is not None:
                    file_age_hours = (now - os.path.getmtime(file_path)) / 3600
                    if file_age_hours < older_than_hours:
                        continue  # Skip newer files
                
                os.remove(file_path)
                log.info(f"已清理临时文件: {filename}")
                cleaned_count += 1
        except OSError as e:
            log.warning(f"清理文件 {filename} 失败: {e}")

    log.info(f"清理完成，共处理 {cleaned_count} 个文件。")

    # 尝试清理空目录
    if not os.listdir(temp_dir):
        try:
            os.rmdir(temp_dir)
            log.info(f"已清理空临时目录: {temp_dir}")
        except OSError as e:
            log.warning(f"清理空目录失败: {e}")

def get_file_size(file_path: str, human_readable: bool = True) -> str:
    """获取文件大小，可选择人类可读格式。"""
    try:
        size_bytes = os.path.getsize(file_path)
        if not human_readable:
            return str(size_bytes)
        
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/1024**2:.2f} MB"
        else:
            return f"{size_bytes/1024**3:.2f} GB"
    except OSError:
        return "N/A"

def get_temp_dir_info() -> dict:
    """获取临时目录信息"""
    temp_dir = get_temp_dir()
    info = {
        "path": temp_dir,
        "exists": os.path.exists(temp_dir),
        "file_count": 0,
        "total_size": 0
    }
    
    if info["exists"]:
        try:
            temp_files = os.listdir(temp_dir)
            info["file_count"] = len(temp_files)
            
            total_size = 0
            for temp_file in temp_files:
                try:
                    total_size += os.path.getsize(os.path.join(temp_dir, temp_file))
                except OSError:
                    pass
            info["total_size"] = total_size
        except Exception:
            pass
    
    return info
