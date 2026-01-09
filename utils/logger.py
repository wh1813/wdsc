"""
日志管理模块
负责统一管理项目的日志记录、存储和查询
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（用于控制台输出）"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        
        return super().format(record)


class Logger:
    """统一日志管理器"""
    
    def __init__(
        self,
        name: str = "DocumentGenerator",
        log_dir: str = "./logs",
        console_level: str = "INFO",
        file_level: str = "DEBUG",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        ui_callback: Optional[Callable] = None
    ):
        """
        初始化日志管理器
        
        Args:
            name: 日志器名称
            log_dir: 日志目录
            console_level: 控制台日志级别
            file_level: 文件日志级别
            max_bytes: 单个日志文件最大字节数
            backup_count: 保留的日志文件数量
            ui_callback: UI回调函数 callback(level, message)
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.ui_callback = ui_callback
        
        # 创建日志器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 1. 控制台处理器
        self._setup_console_handler(console_level)
        
        # 2. 主日志文件处理器（轮转）
        self._setup_main_file_handler(file_level, max_bytes, backup_count)
        
        # 3. 错误日志文件处理器
        self._setup_error_file_handler()
        
        # 4. 按日期轮转的日志处理器
        self._setup_daily_file_handler()
        
        # 日志统计
        self.stats = {
            'debug': 0,
            'info': 0,
            'warning': 0,
            'error': 0,
            'critical': 0,
        }
    
    def _setup_console_handler(self, level: str):
        """设置控制台处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # 使用彩色格式化器
        console_formatter = ColoredFormatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _setup_main_file_handler(self, level: str, max_bytes: int, backup_count: int):
        """设置主日志文件处理器（按大小轮转）"""
        log_file = self.log_dir / f"{self.name}.log"
        
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        # 详细的文件日志格式
        file_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(file_handler)
    
    def _setup_error_file_handler(self):
        """设置错误日志文件处理器（只记录ERROR及以上）"""
        error_log_file = self.log_dir / f"{self.name}_error.log"
        
        error_handler = RotatingFileHandler(
            filename=error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        error_formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        
        self.logger.addHandler(error_handler)
    
    def _setup_daily_file_handler(self):
        """设置按日期轮转的日志处理器"""
        daily_log_file = self.log_dir / f"{self.name}_daily.log"
        
        daily_handler = TimedRotatingFileHandler(
            filename=daily_log_file,
            when='midnight',  # 每天午夜轮转
            interval=1,
            backupCount=30,  # 保留30天
            encoding='utf-8'
        )
        daily_handler.setLevel(logging.INFO)
        
        daily_formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        daily_handler.setFormatter(daily_formatter)
        
        self.logger.addHandler(daily_handler)
    
    def debug(self, message: str, **kwargs):
        """DEBUG级别日志"""
        self.logger.debug(message, **kwargs)
        self.stats['debug'] += 1
        self._call_ui_callback('DEBUG', message)
    
    def info(self, message: str, **kwargs):
        """INFO级别日志"""
        self.logger.info(message, **kwargs)
        self.stats['info'] += 1
        self._call_ui_callback('INFO', message)
    
    def warning(self, message: str, **kwargs):
        """WARNING级别日志"""
        self.logger.warning(message, **kwargs)
        self.stats['warning'] += 1
        self._call_ui_callback('WARNING', message)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """ERROR级别日志"""
        self.logger.error(message, exc_info=exc_info, **kwargs)
        self.stats['error'] += 1
        self._call_ui_callback('ERROR', message)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """CRITICAL级别日志"""
        self.logger.critical(message, exc_info=exc_info, **kwargs)
        self.stats['critical'] += 1
        self._call_ui_callback('CRITICAL', message)
    
    def success(self, message: str):
        """成功消息（INFO级别，特殊标记）"""
        self.logger.info(f"✓ {message}")
        self.stats['info'] += 1
        self._call_ui_callback('SUCCESS', message)
    
    def exception(self, message: str):
        """记录异常信息"""
        self.logger.exception(message)
        self.stats['error'] += 1
        self._call_ui_callback('ERROR', f"{message} (详见日志文件)")
    
    def _call_ui_callback(self, level: str, message: str):
        """调用UI回调"""
        if self.ui_callback:
            try:
                self.ui_callback(level, message)
            except Exception as e:
                # 避免回调错误影响日志记录
                self.logger.error(f"UI回调失败: {str(e)}")
    
    def get_statistics(self) -> dict:
        """获取日志统计信息"""
        return self.stats.copy()
    
    def clear_statistics(self):
        """清空统计信息"""
        for key in self.stats:
            self.stats[key] = 0
    
    def set_level(self, level: str, handler_type: str = 'all'):
        """
        动态设置日志级别
        
        Args:
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            handler_type: 处理器类型 ('console', 'file', 'all')
        """
        log_level = getattr(logging, level.upper())
        
        if handler_type == 'all':
            self.logger.setLevel(log_level)
            for handler in self.logger.handlers:
                handler.setLevel(log_level)
        elif handler_type == 'console':
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setLevel(log_level)
        elif handler_type == 'file':
            for handler in self.logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.setLevel(log_level)
    
    def get_log_files(self) -> list:
        """获取所有日志文件列表"""
        return list(self.log_dir.glob("*.log*"))
    
    def read_log_file(self, file_path: str = None, lines: int = 100) -> list:
        """
        读取日志文件
        
        Args:
            file_path: 日志文件路径，为None则读取主日志
            lines: 读取的行数，-1表示全部
            
        Returns:
            list: 日志行列表
        """
        if file_path is None:
            file_path = self.log_dir / f"{self.name}.log"
        else:
            file_path = Path(file_path)
        
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if lines == -1:
                    return f.readlines()
                else:
                    # 读取最后N行
                    return self._tail(f, lines)
        except Exception as e:
            self.logger.error(f"读取日志文件失败: {str(e)}")
            return []
    
    def _tail(self, file, n: int) -> list:
        """读取文件最后N行"""
        buffer_size = 8192
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        
        lines = []
        buffer = ''
        
        # 从文件末尾向前读取
        for block_num in range(int((file_size + buffer_size - 1) / buffer_size)):
            block_start = max(file_size - (block_num + 1) * buffer_size, 0)
            file.seek(block_start)
            
            buffer = file.read(min(buffer_size, file_size - block_start)) + buffer
            lines = buffer.split('\n')
            
            if len(lines) > n + 1:
                return lines[-n-1:-1]
        
        return lines[-n:] if len(lines) > n else lines
    
    def search_logs(
        self,
        keyword: str,
        level: str = None,
        file_path: str = None,
        max_results: int = 100
    ) -> list:
        """
        搜索日志
        
        Args:
            keyword: 搜索关键词
            level: 日志级别过滤
            file_path: 日志文件路径
            max_results: 最大结果数
            
        Returns:
            list: 匹配的日志行
        """
        lines = self.read_log_file(file_path, lines=-1)
        
        results = []
        for line in lines:
            # 关键词匹配
            if keyword.lower() not in line.lower():
                continue
            
            # 级别过滤
            if level and level.upper() not in line:
                continue
            
            results.append(line)
            
            if len(results) >= max_results:
                break
        
        return results
    
    def export_logs(
        self,
        output_file: str,
        format: str = 'txt',
        level: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> bool:
        """
        导出日志
        
        Args:
            output_file: 输出文件路径
            format: 导出格式 ('txt', 'json', 'csv')
            level: 级别过滤
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            bool: 是否成功
        """
        try:
            lines = self.read_log_file(lines=-1)
            
            # 过滤日志
            filtered_lines = []
            for line in lines:
                # 级别过滤
                if level and level.upper() not in line:
                    continue
                
                # 时间过滤（简单实现，可以优化）
                if start_time or end_time:
                    # 提取时间戳（假设格式: YYYY-MM-DD HH:MM:SS）
                    try:
                        timestamp_str = line.split(' - ')[0]
                        log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        
                        if start_time and log_time < start_time:
                            continue
                        if end_time and log_time > end_time:
                            continue
                    except:
                        pass
                
                filtered_lines.append(line)
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'txt':
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.writelines(filtered_lines)
            
            elif format == 'json':
                # 将日志行转换为JSON格式
                log_entries = []
                for line in filtered_lines:
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        entry = {
                            'timestamp': parts[0].strip(),
                            'level': parts[1].strip(),
                            'message': ' - '.join(parts[2:]).strip()
                        }
                        log_entries.append(entry)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(log_entries, f, ensure_ascii=False, indent=2)
            
            elif format == 'csv':
                import csv
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'Level', 'Message'])
                    
                    for line in filtered_lines:
                        parts = line.split(' - ')
                        if len(parts) >= 3:
                            writer.writerow([
                                parts[0].strip(),
                                parts[1].strip(),
                                ' - '.join(parts[2:]).strip()
                            ])
            
            self.info(f"日志已导出: {output_path}")
            return True
            
        except Exception as e:
            self.error(f"导出日志失败: {str(e)}", exc_info=True)
            return False
    
    def cleanup_old_logs(self, days: int = 30):
        """
        清理旧日志文件
        
        Args:
            days: 保留天数
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            deleted_count = 0
            for log_file in self.log_dir.glob("*.log*"):
                # 跳过主日志文件
                if log_file.name == f"{self.name}.log":
                    continue
                
                # 检查文件修改时间
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
            
            self.info(f"已清理 {deleted_count} 个旧日志文件（超过{days}天）")
            
        except Exception as e:
            self.error(f"清理旧日志失败: {str(e)}")
    
    def get_log_size(self) -> dict:
        """获取日志文件大小信息"""
        total_size = 0
        file_sizes = {}
        
        for log_file in self.log_dir.glob("*.log*"):
            size = log_file.stat().st_size
            total_size += size
            file_sizes[log_file.name] = size
        
        return {
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'file_sizes': file_sizes
        }


# 全局日志器实例
_global_logger = None


def get_logger(
    name: str = "DocumentGenerator",
    log_dir: str = "./logs",
    ui_callback: Optional[Callable] = None
) -> Logger:
    """
    获取全局日志器实例
    
    Args:
        name: 日志器名称
        log_dir: 日志目录
        ui_callback: UI回调函数
        
    Returns:
        Logger: 日志器实例
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = Logger(
            name=name,
            log_dir=log_dir,
            ui_callback=ui_callback
        )
    
    return _global_logger


def setup_logger(config: dict, ui_callback: Optional[Callable] = None) -> Logger:
    """
    根据配置设置日志器
    
    Args:
        config: 配置字典
        ui_callback: UI回调函数
        
    Returns:
        Logger: 日志器实例
    """
    logger = Logger(
        name=config.get('name', 'DocumentGenerator'),
        log_dir=config.get('log_dir', './logs'),
        console_level=config.get('console_level', 'INFO'),
        file_level=config.get('file_level', 'DEBUG'),
        max_bytes=config.get('max_bytes', 10 * 1024 * 1024),
        backup_count=config.get('backup_count', 5),
        ui_callback=ui_callback
    )
    
    return logger
