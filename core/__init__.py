"""
核心模块
包含所有核心功能组件
"""

# 导入核心组件
from core.cookie_manager import CookieManager

try:
    from core.browser_controller import BrowserController
    from core.content_processor import ContentProcessor
    from core.task_manager import TaskManager
except ImportError:
    BrowserController = None
    ContentProcessor = None
    TaskManager = None

__all__ = [
    'CookieManager',
    'BrowserController',
    'ContentProcessor',
    'TaskManager'
]
