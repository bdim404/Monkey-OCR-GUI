"""
国际化支持模块

从JSON文件加载翻译，实现动态语言切换。
"""

import json
import os
from typing import Dict, Any

class I18n:
    """国际化管理类"""
    
    def __init__(self, locales_path: str = 'locales'):
        self.locales_path = locales_path
        self.current_locale = 'zh_CN'  # 默认语言
        self.translations: Dict[str, Dict[str, Any]] = {}
        self._load_translations()
    
    def _load_translations(self):
        """从locales目录加载所有JSON翻译文件"""
        if not os.path.isdir(self.locales_path):
            print(f"[i18n] 错误: 语言目录 '{self.locales_path}' 不存在。")
            return

        for filename in os.listdir(self.locales_path):
            if filename.endswith('.json'):
                locale_name = filename.split('.')[0]
                try:
                    with open(os.path.join(self.locales_path, filename), 'r', encoding='utf-8') as f:
                        self.translations[locale_name] = json.load(f)
                        print(f"[i18n] 成功加载语言: {locale_name}")
                except Exception as e:
                    print(f"[i18n] 错误: 加载 {filename} 失败: {e}")
    
    def set_locale(self, locale: str):
        """设置当前语言"""
        if locale in self.translations:
            self.current_locale = locale
        else:
            print(f"[i18n] 警告: 语言 '{locale}' 不可用，将使用默认语言 '{self.current_locale}'。")
    
    def get_locale(self) -> str:
        """获取当前语言"""
        return self.current_locale
    
    def t(self, key: str, *args, **kwargs) -> str:
        """获取翻译文本，支持格式化"""
        # 优先从当前语言获取翻译
        translations = self.translations.get(self.current_locale, {})
        text = translations.get(key)

        # 如果当前语言没有，尝试从默认语言 (zh_CN) 获取
        if text is None:
            default_translations = self.translations.get('zh_CN', {})
            text = default_translations.get(key, key) # 如果都没有，返回key本身

        # 格式化字符串
        try:
            return text.format(*args, **kwargs)
        except (KeyError, IndexError):
            # 格式化失败时返回原始文本，避免程序崩溃
            return text
    
    def get_available_locales(self) -> list:
        """获取可用语言列表"""
        return sorted(list(self.translations.keys()))


# --- 全局实例和函数 ---

# 确定locales目录的路径（相对于项目根目录）
# __file__ -> i18n.py
# os.path.dirname(__file__) -> src/utils
# os.path.dirname(...) -> src
# os.path.dirname(...) -> project root
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_locales_dir = os.path.join(_project_root, 'locales')

_i18n = I18n(locales_path=_locales_dir)


def t(key: str, *args, **kwargs) -> str:
    """全局翻译函数"""
    return _i18n.t(key, *args, **kwargs)

def set_locale(locale: str):
    """设置全局语言"""
    _i18n.set_locale(locale)

def get_locale() -> str:
    """获取当前语言"""
    return _i18n.get_locale()

def get_available_locales() -> list:
    """获取可用语言列表"""
    return _i18n.get_available_locales()
