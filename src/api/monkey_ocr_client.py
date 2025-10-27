"""
Monkey OCR API 客户端

提供与 Monkey OCR 后端服务交互的功能，包含错误处理、重试机制和日志记录。
"""

import requests
import requests.adapters
import json
import os
import logging
import zipfile
import tempfile
import io
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config.settings import settings

# 配置日志
log = logging.getLogger(__name__)

# --- 自定义异常 ---

class APIError(Exception):
    """API相关错误的基类"""
    pass

class ConnectionError(APIError):
    """网络连接错误"""
    pass

class TimeoutError(APIError):
    """请求超时错误"""
    pass

class APIResponseError(APIError):
    """API返回非200状态码的错误"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


class MonkeyOCRClient:
    """Monkey OCR API 客户端，包含重试和错误处理机制"""
    
    def __init__(self):
        from ..config.settings import settings
        
        self._session = requests.Session()
        # 从配置获取HTTP连接池设置，优化并发性能
        pool_config = settings.get_pool_config()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=pool_config["pool_connections"],  # 连接池数量
            pool_maxsize=pool_config["pool_maxsize"],          # 每个连接池的最大连接数
            max_retries=pool_config["max_retries"]             # 适配器级别重试次数
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    @property
    def base_url(self) -> str:
        """从配置中获取API基础URL"""
        url = settings.get("api.base_url", "").rstrip('/')
        if not url:
            raise APIError("API URL 未在配置中设置。")
        return url
    
    def _get_timeout(self, operation_type: str = "default") -> int:
        """获取特定操作类型的超时时间"""
        return settings.get_timeout(operation_type)
    
    def health_check(self) -> Dict[str, Any]:
        """执行健康检查，返回服务状态"""
        try:
            response = self._session.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()  # 如果状态码不是2xx，则引发HTTPError
            return {"status": "healthy", "data": response.json()}
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"健康检查超时: {e}")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"健康检查连接失败: {e}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"健康检查失败: {e}")

    # 定义重试策略：只对网络相关的可恢复错误进行重试
    _retry_strategy = retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )

    @_retry_strategy
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """文本提取"""
        return self._send_request("/ocr/text", file_path)
    
    @_retry_strategy
    def extract_formula(self, file_path: str) -> Dict[str, Any]:
        """公式提取"""
        return self._send_request("/ocr/formula", file_path)
    
    @_retry_strategy
    def extract_table(self, file_path: str) -> Dict[str, Any]:
        """表格提取"""
        return self._send_request("/ocr/table", file_path)
    
    @_retry_strategy
    def parse_document(self, file_path: str, use_markdown: bool = False) -> Dict[str, Any]:
        """通用文档解析"""
        if use_markdown:
            return self._send_request_with_params("/parse", file_path,
                                                {"return_format": "zip", "return_content": "all"})
        else:
            return self._send_parse_request("/parse", file_path)
    
    @_retry_strategy
    def parse_document_split(self, file_path: str) -> Dict[str, Any]:
        """按页分割的通用文档解析"""
        return self._send_parse_request("/parse/split", file_path)

    def _send_request_with_params(self, endpoint: str, file_path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """发送带有URL参数和文件的POST请求到指定的API端点"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        url = f"{self.base_url}{endpoint}"
        log.info(f"向 {url} 发送请求，参数: {params}")

        try:
            with open(file_path, 'rb') as file:
                files = {'file': (os.path.basename(file_path), file)}
                
                response = self._session.post(
                    url,
                    files=files,
                    params=params,
                    timeout=self._get_timeout("default")
                )

                response.raise_for_status() # 检查HTTP错误

                log.info(f"请求成功，状态码: {response.status_code}")
                result = response.json()

                # 处理文件下载（如果有download_url）
                if result.get('success') and result.get('download_url'):
                    result = self._handle_file_download(result)

                return result

        except requests.exceptions.Timeout as e:
            log.error(f"请求超时: {url}")
            raise TimeoutError(f"请求 {endpoint} 超时") from e
        
        except requests.exceptions.ConnectionError as e:
            log.error(f"连接错误: {url}")
            raise ConnectionError(f"无法连接到 {self.base_url}") from e

        except requests.exceptions.HTTPError as e:
            log.error(f"HTTP错误: {e.response.status_code} - {e.response.text}")
            raise APIResponseError(e.response.status_code, e.response.text) from e

        except Exception as e:
            log.error(f"未知请求异常: {e}")
            raise APIError(f"发生未知错误: {e}") from e

    def _send_request(self, endpoint: str, file_path: str) -> Dict[str, Any]:
        """发送带有文件的POST请求到指定的API端点"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        url = f"{self.base_url}{endpoint}"
        log.info(f"向 {url} 发送请求...")

        try:
            with open(file_path, 'rb') as file:
                files = {'file': (os.path.basename(file_path), file)}
                
                response = self._session.post(
                    url,
                    files=files,
                    timeout=self._get_timeout("default")
                )
                
                response.raise_for_status() # 检查HTTP错误
                
                log.info(f"请求成功，状态码: {response.status_code}")
                return response.json()

        except requests.exceptions.Timeout as e:
            log.error(f"请求超时: {url}")
            raise TimeoutError(f"请求 {endpoint} 超时") from e
        
        except requests.exceptions.ConnectionError as e:
            log.error(f"连接错误: {url}")
            raise ConnectionError(f"无法连接到 {self.base_url}") from e

        except requests.exceptions.HTTPError as e:
            log.error(f"HTTP错误: {e.response.status_code} - {e.response.text}")
            raise APIResponseError(e.response.status_code, e.response.text) from e

        except Exception as e:
            log.error(f"未知请求异常: {e}")
            raise APIError(f"发生未知错误: {e}") from e
    
    def _send_parse_request(self, endpoint: str, file_path: str) -> Dict[str, Any]:
        """发送解析请求到指定的API端点，返回ParseResponse格式"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        url = f"{self.base_url}{endpoint}"
        log.info(f"向 {url} 发送解析请求...")

        try:
            with open(file_path, 'rb') as file:
                files = {'file': (os.path.basename(file_path), file)}
                
                response = self._session.post(
                    url,
                    files=files,
                    timeout=self._get_timeout("document_parse")
                )
                
                response.raise_for_status() # 检查HTTP错误
                
                log.info(f"解析请求成功，状态码: {response.status_code}")
                result = response.json()
                
                # 处理文件下载（如果有download_url）
                if result.get('success') and result.get('download_url'):
                    result = self._handle_file_download(result)
                
                return result

        except requests.exceptions.Timeout as e:
            log.error(f"解析请求超时: {url}")
            raise TimeoutError(f"请求 {endpoint} 超时") from e
        
        except requests.exceptions.ConnectionError as e:
            log.error(f"解析连接错误: {url}")
            raise ConnectionError(f"无法连接到 {self.base_url}") from e

        except requests.exceptions.HTTPError as e:
            log.error(f"解析HTTP错误: {e.response.status_code} - {e.response.text}")
            raise APIResponseError(e.response.status_code, e.response.text) from e

        except Exception as e:
            log.error(f"解析请求异常: {e}")
            raise APIError(f"解析请求发生未知错误: {e}") from e
    
    def _handle_file_download(self, parse_response: Dict[str, Any]) -> Dict[str, Any]:
        """处理解析结果中的文件下载，支持zip解压和.md文件及标记PDF提取"""
        download_url = parse_response.get('download_url')
        if not download_url:
            return parse_response

        try:
            # 处理相对URL：如果URL以'/'开头，则与base_url拼接
            if download_url.startswith('/'):
                download_url = f"{self.base_url}{download_url}"

            # 下载zip文件内容
            response = self._session.get(download_url, timeout=self._get_timeout("file_download"))
            response.raise_for_status()

            log.info(f"成功下载zip文件，大小: {len(response.content)} 字节")

            # 解压zip文件并提取.md文件内容
            markdown_content = self._extract_markdown_from_zip(response.content)

            if markdown_content:
                # 添加提取的markdown内容到结果中
                parse_response['downloaded_content'] = markdown_content
                log.info(f"成功提取markdown内容，大小: {len(markdown_content)} 字符")
            else:
                log.warning("未找到.md文件或提取失败")
                parse_response['downloaded_content'] = "文档解析完成，但未能提取到markdown内容"

            # 提取标记PDF文件
            marked_pdf_path = self._extract_marked_pdf_from_zip(response.content)
            if marked_pdf_path:
                parse_response['marked_pdf_path'] = marked_pdf_path
                log.info(f"成功提取标记PDF: {marked_pdf_path}")
            else:
                log.info("未找到标记PDF文件")

        except Exception as e:
            log.warning(f"下载或处理zip文件失败: {e}")
            # 下载失败不影响主要功能，继续返回原结果

        return parse_response
    
    def _extract_markdown_from_zip(self, zip_content: bytes) -> Optional[str]:
        """从zip文件中提取.md文件内容"""
        try:
            # 使用BytesIO创建一个内存中的zip文件
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
                # 获取zip文件中的所有文件名
                file_names = zip_file.namelist()
                log.info(f"zip文件包含文件: {file_names}")
                
                # 查找.md文件
                md_files = [f for f in file_names if f.endswith('.md')]
                if not md_files:
                    log.warning("zip文件中未找到.md文件")
                    return None
                
                # 使用第一个.md文件
                md_file = md_files[0]
                log.info(f"提取markdown文件: {md_file}")
                
                # 读取.md文件内容
                with zip_file.open(md_file) as file:
                    content = file.read().decode('utf-8')
                    return content
                    
        except Exception as e:
            log.error(f"解压zip文件或提取markdown失败: {e}")
            return None

    def _extract_marked_pdf_from_zip(self, zip_content: bytes) -> Optional[str]:
        """从zip文件中提取标记PDF文件并保存到临时文件"""
        try:
            # 使用BytesIO创建一个内存中的zip文件
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_file:
                # 获取zip文件中的所有文件名
                file_names = zip_file.namelist()

                # 查找PDF文件，优先查找包含"marked"、"annotated"或"labeled"关键词的PDF
                pdf_files = [f for f in file_names if f.endswith('.pdf')]
                if not pdf_files:
                    log.info("zip文件中未找到PDF文件")
                    return None

                # 优先选择带标记关键词的PDF文件
                marked_keywords = ['marked', 'annotated', 'labeled', 'result', 'output']
                marked_pdf = None

                for keyword in marked_keywords:
                    for pdf_file in pdf_files:
                        if keyword in pdf_file.lower():
                            marked_pdf = pdf_file
                            break
                    if marked_pdf:
                        break

                # 如果没找到带关键词的，使用第一个PDF文件
                if not marked_pdf:
                    marked_pdf = pdf_files[0]

                log.info(f"选择标记PDF文件: {marked_pdf}")

                # 创建临时文件保存PDF
                temp_dir = tempfile.gettempdir()
                temp_filename = f"monkey_ocr_marked_{os.getpid()}_{id(zip_content)}.pdf"
                temp_path = os.path.join(temp_dir, temp_filename)

                # 读取PDF文件内容并写入临时文件
                with zip_file.open(marked_pdf) as pdf_file:
                    with open(temp_path, 'wb') as temp_file:
                        temp_file.write(pdf_file.read())

                log.info(f"标记PDF已保存到临时文件: {temp_path}")
                return temp_path

        except Exception as e:
            log.error(f"解压zip文件或提取标记PDF失败: {e}")
            return None
