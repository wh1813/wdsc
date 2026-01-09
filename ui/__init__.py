"""
UI模块
包含所有用户界面组件
"""

# 导入主窗口
from ui.main_window import MainWindow

# 导入模型管理器对话框
try:
    from ui.model_manager_dialog import ModelManagerDialog
except ImportError:
    ModelManagerDialog = None

__all__ = ['MainWindow', 'ModelManagerDialog']
