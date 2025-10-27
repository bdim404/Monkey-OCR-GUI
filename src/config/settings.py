"""
配置管理模块

使用单例模式管理应用程序的设置，支持从JSON文件加载和保存。
"""

import json
import os
import sys
from typing import Dict, Any, Optional

class Settings:
    """应用程序设置管理 (单例)"""
    
    _instance: Optional["Settings"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file: str = "config.json"):
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # 获取正确的配置文件路径
        self.config_file = self._get_config_file_path(config_file)
        self.default_config = self._get_default_config()
        self.config = self.load_config()
        self._initialized = True

    def _get_default_config(self) -> Dict[str, Any]:
        """返回默认配置字典"""
        return {
            "api": {
                "base_url": "",
                "timeout": {
                    "default": 30,
                    "health_check": 10,
                    "document_parse": 60,  # 降低到60秒，避免长时间挂起
                    "file_download": 30    # 降低下载超时
                }
            },
            "ui": {
                "language": "zh_CN",
                "theme": "system",
                "window_width": 1200,
                "window_height": 800,
                "progress_update_delay": 100,  # 进度更新延迟(ms)
                "preview_heights": {
                    "prev_next_ratio": 0.25,   # 上一页/下一页高度比例
                    "current_ratio": 0.5       # 当前页高度比例
                },
                "paddings": {
                    "label_vertical": 14,      # 标签垂直内边距总和
                    "label_horizontal": 10,    # 标签水平内边距总和
                    "frame_padding": 10,       # 框架内边距
                    "small_padding": 5         # 小间距
                },
                "fonts": {
                    "title_size": 14,          # 标题字体大小
                    "button_height": 40,       # 按钮高度
                    "log_text_size": 10,       # 日志文本字体大小
                    "log_height": 150          # 日志区域高度
                },
                "preview": {
                    "default_zoom_level": 1.0,       # 默认缩放级别(100%)
                    "zoom_step": 0.1,                # 细粒度缩放步进值
                    "zoom_step_fast": 0.25,          # 快速缩放步进值
                    "min_zoom": 0.1,                 # 最小缩放级别(10%)
                    "max_zoom": 10.0,                # 最大缩放级别(1000%)
                    "default_fit_to_window": True,   # 默认适应窗口模式
                    "trackpad_sensitivity": 1.5,     # 触控板缩放敏感度
                    "smooth_zoom_enabled": True      # 启用平滑缩放
                }
            },
            "processing": {
                "default_mode": "Text",
                "image_quality": 150  # 调整为更合理的DPI
            },
            "performance": {
                "api": {
                    "pool_connections": 16,  # HTTP连接池数量 - 必须 >= max workers 避免连接饥饿
                    "pool_maxsize": 16,      # 每个连接池的最大连接数
                    "max_retries": 3         # 适配器级别重试次数 - 允许网络重试
                },
                "concurrency": {
                    "pdf_processing_workers": 4,    # PDF处理并发线程数 - CPU密集型，保守值
                    "ocr_processing_workers": 8,    # OCR处理并发线程数 - I/O密集型，适中值
                    "min_workers": 2,               # 最小线程数
                    "max_workers": 16               # 最大线程数限制 - 降低资源压力
                }
            },
            "cache": {
                "auto_cleanup": True,
                "cleanup_on_exit": True,
                "temp_dir_name": "monkey_ocr_temp"
            },
            "logging": {
                "level": "INFO",
                "enabled": True
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件，如果文件不存在或无效，则返回默认配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                merged_config = self._merge_config(self.default_config, user_config)
                return self._validate_config(merged_config)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"警告: 加载配置文件 '{self.config_file}' 失败 ({e})，将使用默认配置。")
                # 在 exe 环境中创建默认配置文件
                if getattr(sys, 'frozen', False):
                    self._create_default_config()
                return self.default_config.copy()
        else:
            # 配置文件不存在，在 exe 环境中创建默认配置
            if getattr(sys, 'frozen', False):
                self._create_default_config()
        return self.default_config.copy()
    
    def _get_config_file_path(self, config_file: str) -> str:
        """获取配置文件的完整路径"""
        # 检测是否在 PyInstaller 打包环境中运行
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包环境，使用可执行文件目录
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境，使用脚本所在目录
            # 从 src/config/settings.py 回到项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        return os.path.join(base_dir, config_file)
    
    def save_config(self):
        """将当前配置保存到文件"""
        try:
            # 确保配置文件目录存在
            config_dir = os.path.dirname(self.config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"错误: 保存配置文件到 '{self.config_file}' 失败: {e}")
    
    def _merge_config(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并用户配置到默认配置，确保所有键都存在"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔的键路径"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值并自动保存，支持点分隔的键路径"""
        keys = key.split('.')
        d = self.config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save_config()

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()

    def _create_default_config(self):
        """创建默认配置文件"""
        try:
            config_dir = os.path.dirname(self.config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.default_config, f, indent=4, ensure_ascii=False)
            print(f"已创建默认配置文件: {self.config_file}")
        except IOError as e:
            print(f"无法创建默认配置文件: {e}")
    
    def reset_to_defaults(self):
        """重置为默认设置并保存"""
        self.config = self.default_config.copy()
        self.save_config()
        print("配置已重置为默认值。")
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证配置值，修复无效的配置"""
        validated = config.copy()
        
        # 验证性能配置
        if "performance" in validated:
            perf = validated["performance"]
            
            # 首先验证并发配置，以确定最大工作线程数
            max_workers = 8  # Default fallback
            if "concurrency" in perf:
                conc = perf["concurrency"]
                max_workers = max(conc.get("ocr_processing_workers", 8), conc.get("pdf_processing_workers", 4))
            
            # API连接池配置验证 - 确保连接池大小 >= 最大工作线程数
            if "api" in perf:
                api = perf["api"]
                min_pool_size = max(max_workers, 8)  # 确保连接池至少等于最大工作线程数
                api["pool_connections"] = max(min_pool_size, min(32, api.get("pool_connections", min_pool_size)))
                api["pool_maxsize"] = max(min_pool_size, min(32, api.get("pool_maxsize", min_pool_size)))
                api["max_retries"] = max(0, min(5, api.get("max_retries", 3)))              # 限制重试次数
            
            # 并发配置验证
            if "concurrency" in perf:
                conc = perf["concurrency"]
                conc["min_workers"] = max(1, min(4, conc.get("min_workers", 2)))
                conc["max_workers"] = max(4, min(64, conc.get("max_workers", 32)))
                conc["pdf_processing_workers"] = max(
                    conc["min_workers"], 
                    min(conc["max_workers"], conc.get("pdf_processing_workers", 8))
                )
                conc["ocr_processing_workers"] = max(
                    conc["min_workers"],
                    min(conc["max_workers"], conc.get("ocr_processing_workers", 16))
                )
        
        # 验证超时配置
        if "api" in validated and "timeout" in validated["api"]:
            timeout = validated["api"]["timeout"]
            if isinstance(timeout, dict):
                for key, value in timeout.items():
                    if isinstance(value, (int, float)):
                        timeout[key] = max(1, min(600, value))  # 1秒到10分钟
        
        # 验证图像质量
        if "processing" in validated:
            processing = validated["processing"]
            if "image_quality" in processing:
                processing["image_quality"] = max(50, min(300, processing["image_quality"]))
        
        return validated

    def get_timeout(self, operation_type: str = "default") -> int:
        """获取特定操作类型的超时时间，支持向后兼容"""
        timeout_config = self.get("api.timeout")
        
        # 向后兼容：如果timeout仍是数字，使用旧格式
        if isinstance(timeout_config, (int, float)):
            if operation_type == "health_check":
                return 10  # 健康检查保持较短超时
            return int(timeout_config)
        
        # 新格式：从嵌套配置获取
        if isinstance(timeout_config, dict):
            return timeout_config.get(operation_type, timeout_config.get("default", 30))
        
        # 兜底默认值
        return 30

    def get_pool_config(self) -> Dict[str, int]:
        """获取HTTP连接池配置，使用保守的默认值"""
        return {
            "pool_connections": self.get("performance.api.pool_connections", 8),  # 降低默认值
            "pool_maxsize": self.get("performance.api.pool_maxsize", 8),         # 降低默认值
            "max_retries": self.get("performance.api.max_retries", 3)             # 保持重试能力
        }
    
    def get_worker_count(self, operation_type: str = "pdf_processing") -> int:
        """获取指定操作类型的工作线程数"""
        import os
        
        if operation_type == "pdf_processing":
            configured = self.get("performance.concurrency.pdf_processing_workers", 8)
        elif operation_type == "ocr_processing":
            configured = self.get("performance.concurrency.ocr_processing_workers", 16)
        else:
            configured = self.get("performance.concurrency.pdf_processing_workers", 8)
        
        min_workers = self.get("performance.concurrency.min_workers", 2)
        max_workers = self.get("performance.concurrency.max_workers", 32)
        cpu_count = os.cpu_count() or 2
        
        # 智能调整：基于CPU核心数和配置的平衡
        if operation_type == "pdf_processing":
            # PDF处理是CPU密集型，不超过CPU核心数
            optimal = min(configured, max(min_workers, cpu_count))
        else:
            # OCR处理是网络I/O密集型，可以使用更多线程
            optimal = min(configured, max(min_workers, cpu_count * 2))
        
        return min(max_workers, optimal)
    
    def validate_system_capabilities(self) -> Dict[str, Any]:
        """验证系统能力并返回建议的配置调整"""
        import os
        import psutil
        
        validation_result = {
            "warnings": [],
            "recommendations": {},
            "system_info": {}
        }
        
        try:
            # 获取系统信息
            cpu_count = os.cpu_count() or 2
            memory_gb = psutil.virtual_memory().total / (1024**3)
            available_memory_gb = psutil.virtual_memory().available / (1024**3)
            
            validation_result["system_info"] = {
                "cpu_cores": cpu_count,
                "total_memory_gb": round(memory_gb, 2),
                "available_memory_gb": round(available_memory_gb, 2)
            }
            
            # 验证内存充足性
            if available_memory_gb < 1.0:
                validation_result["warnings"].append("可用内存不足1GB，可能影响大文档处理")
                validation_result["recommendations"]["reduce_workers"] = True
            
            # 验证连接池配置
            current_pool_size = self.get("performance.api.pool_connections", 8)
            if current_pool_size > cpu_count * 2:
                validation_result["warnings"].append(f"连接池大小({current_pool_size})超过推荐值(CPU核心数x2={cpu_count*2})")
                validation_result["recommendations"]["pool_connections"] = min(16, cpu_count * 2)
            
            # 验证OCR工作线程数
            ocr_workers = self.get("performance.concurrency.ocr_processing_workers", 8)
            if ocr_workers > cpu_count * 4:
                validation_result["warnings"].append(f"OCR工作线程数({ocr_workers})过高，可能导致资源竞争")
                validation_result["recommendations"]["ocr_processing_workers"] = min(16, cpu_count * 2)
            
            # 验证PDF处理线程数
            pdf_workers = self.get("performance.concurrency.pdf_processing_workers", 4)
            if pdf_workers > cpu_count:
                validation_result["warnings"].append(f"PDF处理线程数({pdf_workers})超过CPU核心数({cpu_count})")
                validation_result["recommendations"]["pdf_processing_workers"] = cpu_count
                
        except Exception as e:
            validation_result["warnings"].append(f"系统能力检测失败: {str(e)}")
        
        return validation_result
    
    def apply_system_recommendations(self, validation_result: Dict[str, Any]):
        """应用系统推荐的配置调整"""
        recommendations = validation_result.get("recommendations", {})
        applied_changes = []
        
        for key, value in recommendations.items():
            if key == "reduce_workers":
                # 减少所有工作线程数
                current_ocr = self.get("performance.concurrency.ocr_processing_workers", 8)
                current_pdf = self.get("performance.concurrency.pdf_processing_workers", 4)
                new_ocr = max(2, current_ocr // 2)
                new_pdf = max(1, current_pdf // 2)
                
                self.set("performance.concurrency.ocr_processing_workers", new_ocr)
                self.set("performance.concurrency.pdf_processing_workers", new_pdf)
                applied_changes.append(f"OCR工作线程数: {current_ocr} → {new_ocr}")
                applied_changes.append(f"PDF工作线程数: {current_pdf} → {new_pdf}")
            else:
                # 直接设置推荐值
                current_value = self.get(f"performance.concurrency.{key}" if "workers" in key else f"performance.api.{key}")
                self.set(f"performance.concurrency.{key}" if "workers" in key else f"performance.api.{key}", value)
                applied_changes.append(f"{key}: {current_value} → {value}")
        
        return applied_changes

# 全局单例实例
settings = Settings()
