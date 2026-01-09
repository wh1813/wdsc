"""
浏览器存储管理器
管理Cookie、localStorage、sessionStorage
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable


class BrowserStorageManager:
    """浏览器存储管理器（原CookieManager升级版）"""
    
    def __init__(
        self,
        config_dir: str = './config/accounts',
        log_callback: Optional[Callable] = None
    ):
        """
        初始化存储管理器
        
        Args:
            config_dir: 存储目录
            log_callback: 日志回调函数
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_callback = log_callback
        self.current_account = None
        
        self.log("INFO", f"存储管理器初始化完成，目录: {self.config_dir}")
    
    def log(self, level: str, message: str):
        """记录日志"""
        if self.log_callback:
            self.log_callback(level, message)
    
    def save_account(
        self,
        account_name: str,
        cookies: List[Dict],
        local_storage: Optional[List] = None,
        session_storage: Optional[List] = None
    ) -> bool:
        """
        保存账号的完整浏览器存储
        
        Args:
            account_name: 账号名称
            cookies: Cookie列表
            local_storage: localStorage数据
            session_storage: sessionStorage数据
            
        Returns:
            是否保存成功
        """
        try:
            account_file = self.config_dir / f"{account_name}.json"
            
            # 构建存储数据
            storage_data = {
                'account_name': account_name,
                'cookies': cookies,
                'localStorage': local_storage or [],
                'sessionStorage': session_storage or [],
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'cookie_count': len(cookies),
                'storage_count': {
                    'localStorage': len(local_storage or []),
                    'sessionStorage': len(session_storage or [])
                }
            }
            
            # 保存到文件
            with open(account_file, 'w', encoding='utf-8') as f:
                json.dump(storage_data, f, ensure_ascii=False, indent=2)
            
            self.log("SUCCESS", f"账号 {account_name} 存储已保存")
            self.log("INFO", f"  Cookie: {len(cookies)} 个")
            self.log("INFO", f"  localStorage: {len(local_storage or [])} 项")
            self.log("INFO", f"  sessionStorage: {len(session_storage or [])} 项")
            
            return True
            
        except Exception as e:
            self.log("ERROR", f"保存账号存储失败: {str(e)}")
            return False
    
    def load_account(self, account_name: str) -> Optional[Dict]:
        """
        加载账号的完整存储
        
        Args:
            account_name: 账号名称
            
        Returns:
            存储数据字典，失败返回None
        """
        try:
            account_file = self.config_dir / f"{account_name}.json"
            
            if not account_file.exists():
                self.log("WARNING", f"账号 {account_name} 不存在")
                return None
            
            with open(account_file, 'r', encoding='utf-8') as f:
                storage_data = json.load(f)
            
            self.log("INFO", f"已加载账号: {account_name}")
            
            # 兼容旧版本格式（直接存储cookies列表）
            if isinstance(storage_data, list):
                storage_data = {
                    'account_name': account_name,
                    'cookies': storage_data,
                    'localStorage': [],
                    'sessionStorage': [],
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'cookie_count': len(storage_data),
                    'storage_count': {
                        'localStorage': 0,
                        'sessionStorage': 0
                    }
                }
            # 兼容旧版本格式（只有cookies字段的字典）
            elif isinstance(storage_data, dict) and 'localStorage' not in storage_data:
                storage_data['localStorage'] = []
                storage_data['sessionStorage'] = []
            
            return storage_data
            
        except Exception as e:
            self.log("ERROR", f"加载账号失败: {str(e)}")
            return None
    
    def list_accounts(self) -> List[str]:
        """
        列出所有账号
        
        Returns:
            账号名称列表
        """
        accounts = []
        
        for file_path in self.config_dir.glob("*.json"):
            account_name = file_path.stem
            accounts.append(account_name)
        
        return sorted(accounts)
    
    def delete_account(self, account_name: str) -> bool:
        """
        删除账号
        
        Args:
            account_name: 账号名称
            
        Returns:
            是否删除成功
        """
        try:
            account_file = self.config_dir / f"{account_name}.json"
            
            if not account_file.exists():
                self.log("WARNING", f"账号 {account_name} 不存在")
                return False
            
            account_file.unlink()
            
            if self.current_account == account_name:
                self.current_account = None
            
            self.log("SUCCESS", f"账号 {account_name} 已删除")
            return True
            
        except Exception as e:
            self.log("ERROR", f"删除账号失败: {str(e)}")
            return False
    
    def switch_account(self, account_name: str) -> bool:
        """
        切换当前账号
        
        Args:
            account_name: 账号名称
            
        Returns:
            是否切换成功
        """
        storage_data = self.load_account(account_name)
        
        if storage_data:
            self.current_account = account_name
            self.log("INFO", f"当前账号: {account_name}")
            return True
        else:
            return False
    
    def get_account_info(self, account_name: str) -> Optional[Dict]:
        """
        获取账号详细信息
        
        Args:
            account_name: 账号名称
            
        Returns:
            账号信息字典
        """
        storage_data = self.load_account(account_name)
        
        if not storage_data:
            return None
        
        info = {
            'account_name': account_name,
            'cookie_count': len(storage_data.get('cookies', [])),
            'localStorage_count': len(storage_data.get('localStorage', [])),
            'sessionStorage_count': len(storage_data.get('sessionStorage', [])),
            'created_at': storage_data.get('created_at', 'N/A'),
            'last_updated': storage_data.get('last_updated', 'N/A')
        }
        
        return info


# 保持向后兼容
CookieManager = BrowserStorageManager
