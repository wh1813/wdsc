"""
主窗口 - 最终修复版 (恢复所有UI和功能)
"""
import sys
import json
import asyncio
import os
import re
import socket
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QProgressBar,
    QTabWidget, QGroupBox, QComboBox, QSpinBox,
    QCheckBox, QListWidget, QMessageBox, QFileDialog,
    QDialog, QTableWidget, QTableWidgetItem, QLineEdit,
    QScrollArea, QInputDialog, QApplication
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon, QTextCursor

from core.task_manager import TaskManager
from core.cookie_manager import BrowserStorageManager as StorageManager
from core.browser_controller import BrowserController
from playwright.async_api import async_playwright

def find_free_port():
    """查找一个可用的空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class ManualLoginThread(QThread):
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)
    ready = pyqtSignal()
    
    def __init__(self, website_url):
        super().__init__()
        self.website_url = website_url
        self.confirmed = False
        self.browser = None
        self.playwright = None
        self.port = 0

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.manual_login_async())
            if result.get('success'):
                self.finished.emit(True, result.get('message', '登录成功'))
            else:
                self.finished.emit(False, result.get('message', '登录失败'))
        except Exception as e:
            import traceback
            error_msg = f"登录异常: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
            self.finished.emit(False, error_msg)
        finally:
            loop.close()

    async def manual_login_async(self):
        try:
            self.playwright = await async_playwright().start()
            self.port = find_free_port()
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox', '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    f'--remote-debugging-port={self.port}', '--start-maximized'
                ]
            )
            context = await self.browser.new_context(
                viewport=None, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            await page.goto(self.website_url, timeout=60000, wait_until='domcontentloaded')
            self.ready.emit()
            
            max_wait_time = 600
            while max_wait_time > 0:
                if self.confirmed: break
                if not self.browser.is_connected():
                    return {'success': False, 'message': "浏览器已关闭，登录取消"}
                await asyncio.sleep(0.5)
                max_wait_time -= 0.5

            if not self.confirmed: return {'success': False, 'message': "登录超时 (10分钟)"}
            if 'login' in page.url.lower(): return {'success': False, 'message': "似乎还未登录，请重试"}

            return {'success': True, 'message': "✓ 登录成功！浏览器会话已保持打开"}
        except Exception as e:
            import traceback
            return {'success': False, 'message': f"登录失败: {str(e)}\n{traceback.format_exc()}"}

    def confirm_login(self):
        self.confirmed = True

class TaskThread(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int, int, dict)
    finished_signal = pyqtSignal(dict)
    
    def __init__(self, config, storage_manager, titles, model_name, output_dir, active_session_mode=False, port=0):
        super().__init__()
        self.config = config
        self.storage_manager = storage_manager
        self.titles = titles
        self.model_name = model_name
        self.output_dir = output_dir
        self.task_manager = None
        self.active_session_mode = active_session_mode
        self.port = port

    def run(self):
        try:
            self.task_manager = TaskManager(
                config=self.config, cookie_manager=self.storage_manager, log_callback=self.log_signal.emit
            )
            result = asyncio.run(self.run_task())
            self.finished_signal.emit(result)
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            self.log_signal.emit("ERROR", "TaskThread 中发生未捕获的严重错误:")
            self.log_signal.emit("ERROR", error_msg)
            self.finished_signal.emit({'success': False, 'error': f"发生严重错误: {str(e)}"})
    
    async def run_task(self):
        try:
            init_success = False
            if self.active_session_mode:
                self.log_signal.emit("INFO", f"通过远程端口 {self.port} 连接到活动浏览器...")
                init_success = await self.task_manager.initialize_from_session(port=self.port)
            else:
                self.log_signal.emit("INFO", "使用Cookie模式初始化...")
                current_account = self.storage_manager.current_account or (self.storage_manager.list_accounts() or [None])[0]
                if not current_account: return {'success': False, 'error': '没有可用的账号'}
                init_success = await self.task_manager.initialize(current_account)

            if not init_success: return {'success': False, 'error': '任务管理器初始化失败'}

            result = await self.task_manager.process_batch(
                titles=self.titles, model_name=self.model_name, output_dir=self.output_dir,
                progress_callback=lambda c, t, r: self.progress_signal.emit(c, t, r)
            )
            
            if not self.active_session_mode: await self.task_manager.cleanup()
            return result
        except Exception as e:
            import traceback
            self.log_signal.emit("ERROR", f"run_task 内部发生错误: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    def stop(self):
        if self.task_manager:
            self.log_signal.emit("INFO", "正在请求停止任务...")
            self.task_manager.stop()

class ModelManagerDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.models = config.get('models', []).copy()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("模型管理"); self.setGeometry(200, 200, 800, 500); layout = QVBoxLayout(self)
        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['UI显示名称', 'Web内部名称', '优先级', '启用'])
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table); self.load_models()
        btn_layout = QHBoxLayout(); add_btn = QPushButton("添加"); add_btn.clicked.connect(self.add_model)
        btn_layout.addWidget(add_btn); delete_btn = QPushButton("删除"); delete_btn.clicked.connect(self.delete_model)
        btn_layout.addWidget(delete_btn); btn_layout.addStretch(); save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept); btn_layout.addWidget(save_btn); cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject); btn_layout.addWidget(cancel_btn); layout.addLayout(btn_layout)
    
    def load_models(self):
        self.table.setRowCount(len(self.models));
        for i, model in enumerate(self.models):
            self.table.setItem(i, 0, QTableWidgetItem(model.get('ui_name', ''))); self.table.setItem(i, 1, QTableWidgetItem(model.get('web_name', '')))
            self.table.setItem(i, 2, QTableWidgetItem(str(model.get('priority', 1)))); enabled_check = QCheckBox()
            enabled_check.setChecked(model.get('enabled', True)); self.table.setCellWidget(i, 3, enabled_check)
    
    def add_model(self):
        dialog = QDialog(self); dialog.setWindowTitle("添加模型"); dialog.setGeometry(300, 300, 400, 200); layout = QVBoxLayout(dialog)
        ui_name_layout = QHBoxLayout(); ui_name_layout.addWidget(QLabel("UI显示名称:")); ui_name_input = QLineEdit()
        ui_name_layout.addWidget(ui_name_input); layout.addLayout(ui_name_layout); web_name_layout = QHBoxLayout()
        web_name_layout.addWidget(QLabel("Web内部名称:")); web_name_input = QLineEdit(); web_name_layout.addWidget(web_name_input)
        layout.addLayout(web_name_layout); priority_layout = QHBoxLayout(); priority_layout.addWidget(QLabel("优先级:"))
        priority_spin = QSpinBox(); priority_spin.setRange(1, 100); priority_spin.setValue(1); priority_layout.addWidget(priority_spin)
        layout.addLayout(priority_layout); btn_layout = QHBoxLayout(); ok_btn = QPushButton("确定"); ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn); cancel_btn = QPushButton("取消"); cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn); layout.addLayout(btn_layout)
        if dialog.exec_() == QDialog.Accepted:
            ui_name = ui_name_input.text().strip(); web_name = web_name_input.text().strip()
            if ui_name and web_name:
                new_model = {'ui_name': ui_name, 'web_name': web_name, 'priority': priority_spin.value(), 'enabled': True}
                self.models.append(new_model); self.load_models()
    
    def delete_model(self):
        current_row = self.table.currentRow()
        if current_row >= 0: del self.models[current_row]; self.load_models()
    
    def get_models(self):
        models = [];
        for i in range(self.table.rowCount()):
            models.append({'ui_name': self.table.item(i, 0).text(), 'web_name': self.table.item(i, 1).text(),
                           'priority': int(self.table.item(i, 2).text()), 'enabled': self.table.cellWidget(i, 3).isChecked()})
        return models

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.config = {}; self.cookie_manager = None; self.task_thread = None; self.login_thread = None
        self.login_dialog = None; self.log_buffer = []; self.stats_data = {'success': 0, 'failed': 0}
        self.active_session_mode = False; self.active_session_name = None; self.session_browser_instance = None
        self.active_session_port = 0
        self.current_task_total_titles = []
        self.load_config(); self.cookie_manager = StorageManager(); self.init_ui()
    
    def get_default_config(self):
        return {
            'website_url': 'https://ai.achuanai.cn', 'output_dir': './output', 'log_dir': './logs',
            'default_model': 'GPT-4', 'system_prompt': '你是一个专业的内容创作助手', 'use_new_conversation': True,
            'settings': {
                'interval': 3, 'timeout': 300, 'retry': 3, 'skip_generated': True, 
                'show_browser': False, 'auto_retry_until_complete': False, 'refresh_after_each': False 
            },
            'web_elements': {'input': 'textarea', 'send_button': 'button[type="submit"]', 'model_button': '.model-selector', 'menu': '.model-menu'},
           'models': [
                {'ui_name': 'GPT-4', 'web_name': 'GPT-4', 'priority': 1, 'enabled': True},
                {'ui_name': 'Gemini 1.5 Pro', 'web_name': 'Gemini 1.5 Pro', 'priority': 2, 'enabled': True},
                {'ui_name': 'Claude 3 Sonnet', 'web_name': 'Claude 3 Sonnet', 'priority': 3, 'enabled': True}
            ],
            'word_format': {'font': '宋体', 'font_size': 12, 'line_space': '1.5倍行距', 'add_cover': True, 'add_toc': True},
            'filter_keywords': [], 'filter_regex': [], 'logging': {'save_to_file': True, 'level': 'INFO'}
        }

    def load_config(self):
        config_file = Path('config/config.json')
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f: self.config = json.load(f)
            except Exception: self.config = self.get_default_config()
        else:
            self.config = self.get_default_config(); self.save_config()

    def save_config(self):
        try:
            config_file = Path('config/config.json'); config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f: json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception: return False

    def init_ui(self):
        self.setWindowTitle("AI文档批量生成工具 v2.9"); self.setGeometry(100, 100, 1400, 900)
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget)
        toolbar_layout = QHBoxLayout(); account_group = QGroupBox("账号管理"); account_layout = QHBoxLayout(account_group)
        account_layout.addWidget(QLabel("当前账号:")); self.account_combo = QComboBox(); self.account_combo.currentTextChanged.connect(self.on_account_changed)
        account_layout.addWidget(self.account_combo); self.cookie_status_label = QLabel("状态: 未登录"); account_layout.addWidget(self.cookie_status_label)
        manual_login_btn = QPushButton("手动登录"); manual_login_btn.clicked.connect(self.manual_login); account_layout.addWidget(manual_login_btn)
        delete_account_btn = QPushButton("删除账号"); delete_account_btn.clicked.connect(self.delete_account); account_layout.addWidget(delete_account_btn)
        export_account_btn = QPushButton("导出账号"); export_account_btn.clicked.connect(self.export_account); account_layout.addWidget(export_account_btn)
        copy_cookies_btn = QPushButton("复制Cookie"); copy_cookies_btn.clicked.connect(self.copy_cookies); account_layout.addWidget(copy_cookies_btn)
        toolbar_layout.addWidget(account_group); main_layout.addLayout(toolbar_layout); self.tab_widget = QTabWidget()
        self.create_main_tab(); self.create_account_tab(); self.create_settings_tab(); self.create_stats_tab(); self.create_filter_tab(); self.create_log_tab()
        main_layout.addWidget(self.tab_widget); status_layout = QHBoxLayout(); self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label); self.progress_bar = QProgressBar(); status_layout.addWidget(self.progress_bar)
        main_layout.addLayout(status_layout); self.update_account_combo()

    def create_main_tab(self):
        main_tab = QWidget(); layout = QVBoxLayout(main_tab); title_group = QGroupBox("标题输入"); title_layout = QVBoxLayout(title_group)
        btn_layout = QHBoxLayout(); import_btn = QPushButton("从文件导入"); import_btn.clicked.connect(self.import_titles); btn_layout.addWidget(import_btn)
        batch_btn = QPushButton("批量生成标题"); batch_btn.clicked.connect(self.batch_input_titles); btn_layout.addWidget(batch_btn)
        btn_layout.addStretch(); title_layout.addLayout(btn_layout); self.title_input = QTextEdit()
        self.title_input.setPlaceholderText("每行一个标题..."); title_layout.addWidget(self.title_input); layout.addWidget(title_group)
        settings_group = QGroupBox("生成设置"); settings_layout = QVBoxLayout(settings_group); model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("选择模型:")); self.model_combo = QComboBox(); self.reload_model_list(); model_layout.addWidget(self.model_combo)
        manage_model_btn = QPushButton("管理模型"); manage_model_btn.clicked.connect(self.open_model_manager); model_layout.addWidget(manage_model_btn)
        model_layout.addStretch(); settings_layout.addLayout(model_layout)
        self.auto_retry_check = QCheckBox("自动重试直至全部完成"); self.auto_retry_check.setChecked(self.config.get('settings', {}).get('auto_retry_until_complete', False)); settings_layout.addWidget(self.auto_retry_check)
        output_layout = QHBoxLayout(); output_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_input = QLineEdit(); self.output_dir_input.setText(self.config.get('output_dir', './output')); output_layout.addWidget(self.output_dir_input)
        browse_btn = QPushButton("浏览"); browse_btn.clicked.connect(self.browse_output_dir); output_layout.addWidget(browse_btn)
        settings_layout.addLayout(output_layout); layout.addWidget(settings_group); control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始生成"); self.start_btn.setStyleSheet("font-size: 16px; padding: 10px;"); self.start_btn.clicked.connect(self.start_task)
        control_layout.addWidget(self.start_btn)
        self.stop_btn = QPushButton("停止"); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_task)
        control_layout.addWidget(self.stop_btn)
        layout.addLayout(control_layout); self.tab_widget.addTab(main_tab, "主界面")

    def create_account_tab(self):
        account_tab = QWidget(); layout = QVBoxLayout(account_tab); info_group = QGroupBox("账号信息"); info_layout = QVBoxLayout(info_group)
        self.cookie_text = QTextEdit(); self.cookie_text.setReadOnly(True); info_layout.addWidget(self.cookie_text)
        layout.addWidget(info_group); self.tab_widget.addTab(account_tab, "账号管理")

    def create_settings_tab(self):
        settings_tab = QWidget(); scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll_widget = QWidget(); layout = QVBoxLayout(scroll_widget)
        basic_group = QGroupBox("基本设置"); basic_layout = QVBoxLayout(basic_group); interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("请求间隔(秒):")); self.interval_spin = QSpinBox(); self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(self.config['settings']['interval']); interval_layout.addWidget(self.interval_spin); interval_layout.addStretch()
        basic_layout.addLayout(interval_layout); timeout_layout = QHBoxLayout(); timeout_layout.addWidget(QLabel("超时时间(秒):"))
        self.timeout_spin = QSpinBox(); self.timeout_spin.setRange(30, 600); self.timeout_spin.setValue(self.config['settings']['timeout'])
        timeout_layout.addWidget(self.timeout_spin); timeout_layout.addStretch(); basic_layout.addLayout(timeout_layout)
        self.skip_generated_check = QCheckBox("跳过已生成的文件"); self.skip_generated_check.setChecked(self.config['settings']['skip_generated']); basic_layout.addWidget(self.skip_generated_check)
        self.show_browser_check = QCheckBox("显示浏览器窗口"); self.show_browser_check.setChecked(self.config['settings']['show_browser']); basic_layout.addWidget(self.show_browser_check)
        self.refresh_each_check = QCheckBox("每次生成后刷新页面 (强力防卡死)"); self.refresh_each_check.setChecked(self.config.get('settings', {}).get('refresh_after_each', False)); basic_layout.addWidget(self.refresh_each_check)
        layout.addWidget(basic_group)
        
        ai_group = QGroupBox("AI设置"); ai_layout = QVBoxLayout(ai_group)
        ai_layout.addWidget(QLabel("系统提示词 (System Prompt):")); self.system_prompt_text = QTextEdit(); self.system_prompt_text.setPlainText(self.config.get('system_prompt', ''))
        self.system_prompt_text.setMaximumHeight(100); ai_layout.addWidget(self.system_prompt_text); self.new_conversation_check = QCheckBox("每个标题使用新对话")
        self.new_conversation_check.setChecked(self.config.get('use_new_conversation', True)); ai_layout.addWidget(self.new_conversation_check); layout.addWidget(ai_group)
        
        word_group = QGroupBox("Word格式设置"); word_layout = QVBoxLayout(word_group)
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("字体:")); self.font_combo = QComboBox(); self.font_combo.addItems(['宋体', '黑体', '微软雅黑', 'Arial', 'Times New Roman'])
        self.font_combo.setCurrentText(self.config['word_format']['font']); font_layout.addWidget(self.font_combo); font_layout.addStretch(); word_layout.addLayout(font_layout)
        font_size_layout = QHBoxLayout(); font_size_layout.addWidget(QLabel("字号:")); self.font_size_spin = QSpinBox(); self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(self.config['word_format']['font_size']); font_size_layout.addWidget(self.font_size_spin); font_size_layout.addStretch()
        word_layout.addLayout(font_size_layout); line_space_layout = QHBoxLayout(); line_space_layout.addWidget(QLabel("行距:"))
        self.line_space_combo = QComboBox(); self.line_space_combo.addItems(['单倍行距', '1.5倍行距', '2倍行距']); self.line_space_combo.setCurrentText(self.config['word_format']['line_space'])
        line_space_layout.addWidget(self.line_space_combo); line_space_layout.addStretch(); word_layout.addLayout(line_space_layout)
        self.add_cover_check = QCheckBox("添加封面"); self.add_cover_check.setChecked(self.config['word_format']['add_cover']); word_layout.addWidget(self.add_cover_check)
        self.add_toc_check = QCheckBox("添加目录"); self.add_toc_check.setChecked(self.config['word_format']['add_toc']); word_layout.addWidget(self.add_toc_check)
        layout.addWidget(word_group)
        
        btn_layout = QHBoxLayout(); save_btn = QPushButton("保存设置"); save_btn.clicked.connect(self.save_config_from_ui); btn_layout.addWidget(save_btn)
        reset_btn = QPushButton("恢复默认"); reset_btn.clicked.connect(self.reset_config); btn_layout.addWidget(reset_btn)
        layout.addLayout(btn_layout); scroll.setWidget(scroll_widget); tab_layout = QVBoxLayout(settings_tab); tab_layout.addWidget(scroll); self.tab_widget.addTab(settings_tab, "设置")

    def create_stats_tab(self):
        stats_tab = QWidget(); layout = QVBoxLayout(stats_tab);
        self.stats_text = QTextEdit(); self.stats_text.setReadOnly(True); layout.addWidget(self.stats_text)
        self.refresh_stats(); self.tab_widget.addTab(stats_tab, "统计")
    
    def create_filter_tab(self):
        filter_tab = QWidget(); layout = QVBoxLayout(filter_tab)
        keyword_group = QGroupBox("关键词过滤"); keyword_layout = QVBoxLayout(keyword_group)
        self.filter_keywords_text = QTextEdit(); self.filter_keywords_text.setPlainText('\n'.join(self.config.get('filter_keywords', []))); keyword_layout.addWidget(self.filter_keywords_text)
        layout.addWidget(keyword_group)
        save_filter_btn = QPushButton("保存过滤规则"); save_filter_btn.clicked.connect(self.save_filter_rules); layout.addWidget(save_filter_btn)
        self.tab_widget.addTab(filter_tab, "过滤规则")

    def create_log_tab(self):
        log_tab = QWidget(); layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True); layout.addWidget(self.log_text)
        self.tab_widget.addTab(log_tab, "运行日志")

    def reload_model_list(self):
        self.model_combo.clear(); enabled_models = [m for m in self.config.get('models', []) if m.get('enabled', True)]
        enabled_models.sort(key=lambda x: x.get('priority', 999));
        for model in enabled_models: self.model_combo.addItem(model['ui_name'])

    def on_login_finished(self, success, message):
        if self.login_dialog: self.login_dialog.close()
        if success:
            account_name = getattr(self, 'pending_account_name', f'会话_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            self.active_session_mode = True; self.active_session_name = account_name
            self.session_browser_instance = self.login_thread.browser; self.active_session_port = self.login_thread.port
            self.account_combo.clear(); self.account_combo.addItem(f"活动会话: {account_name}")
            self.cookie_status_label.setText("状态: 🟢 会话活动中")
            self.cookie_text.setText(f"会话: {account_name}\n模式: 保持浏览器会话")
        else:
            QMessageBox.warning(self, "登录失败", message)

    def start_task(self):
        all_titles = [t.strip() for t in self.title_input.toPlainText().strip().split('\n') if t.strip()]
        if not all_titles: return
        
        if not self.current_task_total_titles: self.current_task_total_titles = all_titles

        if self.active_session_mode and (not self.session_browser_instance or not self.session_browser_instance.is_connected()):
            QMessageBox.warning(self, "会话失效", "浏览器会话已关闭。"); self.active_session_mode = False; self.update_account_combo(); return
        
        if not self.active_session_mode and not self.account_combo.currentText():
             QMessageBox.warning(self, "提示", "请先登录或选择账号"); return
        
        self.save_config_from_ui()
        
        titles_to_process = []
        if self.config.get('settings', {}).get('skip_generated', True):
            self.add_log("INFO", "启用“跳过已生成文件”功能，正在检查...")
            output_path = Path(self.output_dir_input.text())
            existing_files = {f.stem for f in output_path.glob('*.docx')} if output_path.exists() else set()
            skipped_count = 0
            for title in all_titles:
                safe_title = re.sub(r'[\\/:*?"<>|\r\n]', "_", title).strip()[:100]
                if safe_title in existing_files:
                    skipped_count += 1
                else:
                    titles_to_process.append(title)
            if skipped_count > 0:
                self.add_log("INFO", f"已跳过 {skipped_count} 个已存在的文档。")
        else:
            titles_to_process = all_titles

        if not titles_to_process:
            self.add_log("SUCCESS", "所有标题均已生成，任务无需启动。")
            QMessageBox.information(self, "任务提示", "所有标题均已生成。")
            if self.auto_retry_check.isChecked(): self.on_task_finished({'success': 0, 'failed': 0, 'details': []})
            return

        self.task_thread = TaskThread(self.config, self.cookie_manager, titles_to_process, self.model_combo.currentText(), self.output_dir_input.text(), self.active_session_mode, self.active_session_port)
        self.task_thread.log_signal.connect(self.add_log); self.task_thread.progress_signal.connect(self.update_progress); self.task_thread.finished_signal.connect(self.on_task_finished)
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(titles_to_process))
        self.add_log("SUCCESS", f"任务启动，本次需处理 {len(titles_to_process)} 个标题。")
        self.task_thread.start()

    def stop_task(self):
        if self.task_thread and self.task_thread.isRunning():
            self.task_thread.stop()
            self.stop_btn.setEnabled(False)
            self.status_label.setText("正在停止...")

    def on_task_finished(self, result):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status_label.setText("任务完成")
        self.refresh_stats()
        
        if result.get('error'):
            self.add_log("ERROR", f"任务因错误中止: {result.get('error')}")
            if "中止" in result.get('error', ''):
                QMessageBox.warning(self, "任务中止", f"任务已中止:\n\n{result.get('error')}")

        if self.auto_retry_check.isChecked() and not "中止" in result.get('error', ''):
            missing_titles = self._get_missing_titles()
            if not missing_titles:
                self.current_task_total_titles = []
                self.add_log("SUCCESS", "扫描确认：所有标题均已生成完毕！")
                QMessageBox.information(self, "全部完成", "所有标题均已成功生成文档！")
            else:
                self.add_log("WARNING", f"检测到 {len(missing_titles)} 个标题未完成，5秒后开始重试...")
                QTimer.singleShot(5000, lambda: self._start_retry_task(missing_titles))
        else:
            self.current_task_total_titles = []

    def _get_missing_titles(self) -> list:
        if not self.current_task_total_titles: return []
        output_path = Path(self.output_dir_input.text())
        existing_files = {f.stem for f in output_path.glob('*.docx')} if output_path.exists() else set()
        return [title for title in self.current_task_total_titles if re.sub(r'[\\/:*?"<>|\r\n]', "_", title).strip()[:100] not in existing_files]

    def _start_retry_task(self, missing_titles: list):
        self.title_input.setPlainText("\n".join(missing_titles)); self.start_task()

    def update_progress(self, current, total, result):
        self.progress_bar.setValue(current); self.status_label.setText(f"进度: {current}/{total}")
    
    def on_account_changed(self, account_name: str):
        if not account_name or account_name.startswith("活动会话:"): return
        self.active_session_mode = False
        self.cookie_manager.current_account = account_name
        storage_data = self.cookie_manager.load_account(account_name)
        if storage_data:
            self.cookie_status_label.setText("状态: ✅ 已保存")
            self.cookie_text.setText(f"账号: {account_name}\nCookies: {len(storage_data.get('cookies', []))}个")
        else:
            self.cookie_status_label.setText("状态: ❌ 数据丢失")

    def update_account_combo(self):
        self.account_combo.clear(); accounts = self.cookie_manager.list_accounts()
        if accounts:
            self.account_combo.addItems(accounts)
            if self.cookie_manager.current_account in accounts:
                self.account_combo.setCurrentText(self.cookie_manager.current_account)
            else:
                self.account_combo.setCurrentIndex(0)
        else:
            self.cookie_status_label.setText("状态: ❌ 无账号")

    def manual_login(self):
        account_name, ok = QInputDialog.getText(self, "手动登录", "请输入会话名称:", text=f"会话_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if not ok or not account_name.strip(): return
        self.pending_account_name = account_name.strip()
        self.login_dialog = QDialog(self); self.login_dialog.setWindowTitle("手动登录"); self.login_dialog.setGeometry(300, 300, 400, 150)
        layout = QVBoxLayout(self.login_dialog); label = QLabel("浏览器将打开，请手动完成登录后点击【确认登录】"); label.setWordWrap(True)
        layout.addWidget(label); self.login_status_label = QLabel("状态: 正在启动浏览器..."); layout.addWidget(self.login_status_label)
        btn_layout = QHBoxLayout(); self.login_confirm_btn = QPushButton("确认登录"); self.login_confirm_btn.setEnabled(False)
        self.login_confirm_btn.clicked.connect(self.confirm_login); btn_layout.addWidget(self.login_confirm_btn)
        cancel_btn = QPushButton("取消"); cancel_btn.clicked.connect(self.cancel_login); btn_layout.addWidget(cancel_btn); layout.addLayout(btn_layout)
        self.login_thread = ManualLoginThread(self.config.get('website_url', '')); self.login_thread.ready.connect(self.on_login_ready)
        self.login_thread.finished.connect(self.on_login_finished); self.login_thread.error.connect(self.on_login_error)
        self.login_thread.start(); self.login_dialog.exec_()
        
    def on_login_ready(self):
        if self.login_dialog: self.login_status_label.setText("状态: ✅ 浏览器已打开"); self.login_confirm_btn.setEnabled(True)
        
    def confirm_login(self):
        if self.login_thread: self.login_thread.confirm_login(); self.login_status_label.setText("状态: 正在保存..."); self.login_confirm_btn.setEnabled(False)
        
    def cancel_login(self):
        if self.login_thread and self.login_thread.isRunning():
            if self.login_thread.browser and self.login_thread.browser.is_connected(): asyncio.run(self.login_thread.browser.close())
            self.login_thread.quit(); self.login_thread.wait()
        if self.login_dialog: self.login_dialog.close()
        self.add_log("WARNING", "登录已取消")
        
    def on_login_error(self, error_msg):
        self.add_log("ERROR", error_msg)
        if self.login_dialog: self.login_status_label.setText(f"状态: ❌ {error_msg[:50]}")

    def delete_account(self):
        account_name = self.account_combo.currentText()
        if account_name and not account_name.startswith("活动会话:") and QMessageBox.question(self, "确认删除", f"确定要删除账号 '{account_name}' 吗？") == QMessageBox.Yes:
            if self.cookie_manager.delete_account(account_name):
                self.add_log("SUCCESS", f"账号 '{account_name}' 已删除")
                self.update_account_combo()

    def export_account(self):
        account_name = self.account_combo.currentText()
        if not account_name or account_name.startswith("活动会话:"): return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出账号", f"{account_name}.json", "JSON文件 (*.json)")
        if file_path:
            storage_data = self.cookie_manager.load_account(account_name)
            if storage_data:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f: json.dump(storage_data, f, ensure_ascii=False, indent=2)
                    self.add_log("SUCCESS", f"账号已导出到: {file_path}")
                except Exception as e: self.add_log("ERROR", f"导出失败: {e}")

    def copy_cookies(self):
        account_name = self.account_combo.currentText()
        if not account_name or account_name.startswith("活动会话:"): return
        storage_data = self.cookie_manager.load_account(account_name)
        if storage_data and storage_data.get('cookies'):
            QApplication.clipboard().setText(json.dumps(storage_data['cookies']))
            self.add_log("SUCCESS", "Cookies已复制到剪贴板")

    def import_titles(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入标题", "", "文本文件 (*.txt)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f: self.title_input.setPlainText(f.read())
                self.add_log("SUCCESS", f"已从 {os.path.basename(file_path)} 导入标题。")
            except Exception as e:
                self.add_log("ERROR", f"导入失败: {e}")

    def batch_input_titles(self):
        base_title, ok = QInputDialog.getText(self, "批量生成标题", "基础标题:")
        if ok and base_title:
            count, ok = QInputDialog.getInt(self, "批量生成标题", "生成数量:", 10, 1, 1000)
            if ok:
                titles = [f"{base_title} {i+1}" for i in range(count)]
                current_text = self.title_input.toPlainText().strip()
                if current_text:
                    self.title_input.setPlainText(current_text + "\n" + "\n".join(titles))
                else:
                    self.title_input.setPlainText("\n".join(titles))
                self.add_log("SUCCESS", f"已生成 {count} 个标题。")

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_input.text())
        if dir_path: self.output_dir_input.setText(dir_path)

    def open_model_manager(self):
        dialog = ModelManagerDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config['models'] = dialog.get_models(); self.save_config(); self.reload_model_list()

    def save_config_from_ui(self):
        self.config['settings']['interval'] = self.interval_spin.value()
        self.config['settings']['timeout'] = self.timeout_spin.value()
        self.config['settings']['skip_generated'] = self.skip_generated_check.isChecked()
        self.config['settings']['show_browser'] = self.show_browser_check.isChecked()
        self.config['settings']['auto_retry_until_complete'] = self.auto_retry_check.isChecked()
        self.config['settings']['refresh_after_each'] = self.refresh_each_check.isChecked()
        self.config['system_prompt'] = self.system_prompt_text.toPlainText()
        self.config['use_new_conversation'] = self.new_conversation_check.isChecked()
        self.config['word_format']['font'] = self.font_combo.currentText()
        self.config['word_format']['font_size'] = self.font_size_spin.value()
        self.config['word_format']['line_space'] = self.line_space_combo.currentText()
        self.config['word_format']['add_cover'] = self.add_cover_check.isChecked()
        self.config['word_format']['add_toc'] = self.add_toc_check.isChecked()
        self.config['output_dir'] = self.output_dir_input.text()
        self.save_config(); self.add_log("SUCCESS", "配置已保存。")
    
    def reset_config(self):
        if QMessageBox.question(self, "确认", "确定要恢复默认配置吗？") == QMessageBox.Yes:
            self.config = self.get_default_config(); self.save_config()
            self.interval_spin.setValue(self.config['settings']['interval'])
            self.timeout_spin.setValue(self.config['settings']['timeout'])
            self.skip_generated_check.setChecked(self.config['settings']['skip_generated'])
            self.show_browser_check.setChecked(self.config['settings']['show_browser'])
            self.refresh_each_check.setChecked(self.config['settings']['refresh_after_each'])
            self.system_prompt_text.setPlainText(self.config.get('system_prompt', ''))
            self.new_conversation_check.setChecked(self.config.get('use_new_conversation', True))
            self.font_combo.setCurrentText(self.config['word_format']['font'])
            self.font_size_spin.setValue(self.config['word_format']['font_size'])
            self.line_space_combo.setCurrentText(self.config['word_format']['line_space'])
            self.add_cover_check.setChecked(self.config['word_format']['add_cover'])
            self.add_toc_check.setChecked(self.config['word_format']['add_toc'])
            self.add_log("SUCCESS", "配置已恢复为默认值。")
    
    def refresh_stats(self):
        output_dir = Path(self.config.get('output_dir', './output'))
        if not output_dir.exists(): return
        files = list(output_dir.glob('*.docx'))
        self.stats_text.setText(f"已生成文件数: {len(files)}")

    def save_filter_rules(self):
        self.config['filter_keywords'] = [k.strip() for k in self.filter_keywords_text.toPlainText().split('\n') if k.strip()]
        self.save_config(); QMessageBox.information(self, "成功", "过滤规则已保存")

    def add_log(self, level, message):
        log_line = f'[{datetime.now().strftime("%H:%M:%S")}] [{level}] {message}'
        if hasattr(self, 'log_text'): self.log_text.append(log_line)
        else: self.log_buffer.append(log_line)
        print(log_line)

    def closeEvent(self, event):
        if self.task_thread and self.task_thread.isRunning():
            self.stop_task()
            self.task_thread.wait(3000)
        if self.active_session_mode and self.session_browser_instance and self.session_browser_instance.is_connected():
            if QMessageBox.question(self, "确认退出", "退出将关闭活动浏览器，确定吗？") == QMessageBox.No:
                event.ignore(); return
            asyncio.run(self.session_browser_instance.close())
        event.accept()
