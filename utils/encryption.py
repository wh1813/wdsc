"""
加密工具模块
负责敏感信息的加密、解密和密钥管理
"""
import os
import base64
import json
from pathlib import Path
from typing import Optional, Union, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend


class Encryption:
    """加密工具类"""
    
    def __init__(self, key_file: str = "./config/.key", password: str = None):
        """
        初始化加密工具
        
        Args:
            key_file: 密钥文件路径
            password: 用户密码（可选，用于派生密钥）
        """
        self.key_file = Path(key_file)
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载或生成密钥
        if password:
            self.key = self._derive_key_from_password(password)
        else:
            self.key = self._load_or_generate_key()
        
        # 创建Fernet实例
        self.cipher = Fernet(self.key)
    
    def _load_or_generate_key(self) -> bytes:
        """加载或生成密钥"""
        if self.key_file.exists():
            # 加载已有密钥
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            # 生成新密钥
            key = Fernet.generate_key()
            
            # 保存密钥
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # 设置文件权限（仅所有者可读写）
            os.chmod(self.key_file, 0o600)
            
            return key
    
    def _derive_key_from_password(self, password: str, salt: bytes = None) -> bytes:
        """
        从密码派生密钥
        
        Args:
            password: 用户密码
            salt: 盐值（可选）
            
        Returns:
            bytes: 派生的密钥
        """
        if salt is None:
            # 使用固定盐值（实际应用中应该为每个用户生成唯一盐值）
            salt = b'document_generator_salt_2025'
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_string(self, plaintext: str) -> str:
        """
        加密字符串
        
        Args:
            plaintext: 明文字符串
            
        Returns:
            str: 加密后的字符串（Base64编码）
        """
        if not plaintext:
            return ""
        
        # 加密
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        
        # Base64编码
        return base64.urlsafe_b64encode(encrypted_bytes).decode()
    
    def decrypt_string(self, encrypted_text: str) -> str:
        """
        解密字符串
        
        Args:
            encrypted_text: 加密的字符串（Base64编码）
            
        Returns:
            str: 解密后的明文
        """
        if not encrypted_text:
            return ""
        
        try:
            # Base64解码
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            
            # 解密
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            
            return decrypted_bytes.decode()
            
        except Exception as e:
            raise ValueError(f"解密失败: {str(e)}")
    
    def encrypt_dict(self, data: Dict) -> str:
        """
        加密字典对象
        
        Args:
            data: 字典数据
            
        Returns:
            str: 加密后的JSON字符串（Base64编码）
        """
        if not data:
            return ""
        
        # 转换为JSON
        json_str = json.dumps(data, ensure_ascii=False)
        
        # 加密
        return self.encrypt_string(json_str)
    
    def decrypt_dict(self, encrypted_text: str) -> Dict:
        """
        解密字典对象
        
        Args:
            encrypted_text: 加密的字符串
            
        Returns:
            Dict: 解密后的字典
        """
        if not encrypted_text:
            return {}
        
        # 解密
        json_str = self.decrypt_string(encrypted_text)
        
        # 解析JSON
        return json.loads(json_str)
    
    def encrypt_file(self, input_file: str, output_file: str = None) -> str:
        """
        加密文件
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径（可选，默认为输入文件+.enc）
            
        Returns:
            str: 输出文件路径
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_file}")
        
        # 确定输出文件路径
        if output_file is None:
            output_path = input_path.with_suffix(input_path.suffix + '.enc')
        else:
            output_path = Path(output_file)
        
        # 读取文件内容
        with open(input_path, 'rb') as f:
            data = f.read()
        
        # 加密
        encrypted_data = self.cipher.encrypt(data)
        
        # 写入加密文件
        with open(output_path, 'wb') as f:
            f.write(encrypted_data)
        
        return str(output_path)
    
    def decrypt_file(self, input_file: str, output_file: str = None) -> str:
        """
        解密文件
        
        Args:
            input_file: 加密的文件路径
            output_file: 输出文件路径（可选）
            
        Returns:
            str: 输出文件路径
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_file}")
        
        # 确定输出文件路径
        if output_file is None:
            # 如果输入文件以.enc结尾，移除它
            if input_path.suffix == '.enc':
                output_path = input_path.with_suffix('')
            else:
                output_path = input_path.with_suffix('.dec')
        else:
            output_path = Path(output_file)
        
        # 读取加密文件
        with open(input_path, 'rb') as f:
            encrypted_data = f.read()
        
        # 解密
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data)
        except Exception as e:
            raise ValueError(f"解密失败: {str(e)}")
        
        # 写入解密文件
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
        
        return str(output_path)
    
    def encrypt_cookies(self, cookies: list) -> str:
        """
        加密Cookies列表
        
        Args:
            cookies: Cookies列表
            
        Returns:
            str: 加密后的字符串
        """
        return self.encrypt_dict({'cookies': cookies})
    
    def decrypt_cookies(self, encrypted_text: str) -> list:
        """
        解密Cookies列表
        
        Args:
            encrypted_text: 加密的字符串
            
        Returns:
            list: Cookies列表
        """
        data = self.decrypt_dict(encrypted_text)
        return data.get('cookies', [])
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        更改密码（重新加密密钥）
        
        Args:
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            bool: 是否成功
        """
        try:
            # 使用旧密码派生密钥
            old_key = self._derive_key_from_password(old_password)
            old_cipher = Fernet(old_key)
            
            # 读取并解密当前密钥文件
            if self.key_file.exists():
                with open(self.key_file, 'rb') as f:
                    encrypted_key = f.read()
                
                # 尝试解密（验证旧密码）
                try:
                    decrypted_key = old_cipher.decrypt(encrypted_key)
                except:
                    return False  # 旧密码错误
            else:
                # 如果没有密钥文件，使用当前密钥
                decrypted_key = self.key
            
            # 使用新密码派生新密钥
            new_key = self._derive_key_from_password(new_password)
            new_cipher = Fernet(new_key)
            
            # 用新密钥加密原始密钥
            encrypted_key = new_cipher.encrypt(decrypted_key)
            
            # 保存
            with open(self.key_file, 'wb') as f:
                f.write(encrypted_key)
            
            # 更新当前密钥
            self.key = new_key
            self.cipher = Fernet(self.key)
            
            return True
            
        except Exception as e:
            print(f"更改密码失败: {str(e)}")
            return False
    
    def generate_new_key(self) -> bytes:
        """
        生成新的加密密钥
        
        Returns:
            bytes: 新密钥
        """
        key = Fernet.generate_key()
        return key
    
    def export_key(self, output_file: str, password: str = None):
        """
        导出密钥
        
        Args:
            output_file: 输出文件路径
            password: 密码保护（可选）
        """
        if password:
            # 使用密码加密密钥
            cipher = Fernet(self._derive_key_from_password(password))
            encrypted_key = cipher.encrypt(self.key)
            data = encrypted_key
        else:
            data = self.key
        
        with open(output_file, 'wb') as f:
            f.write(data)
    
    def import_key(self, input_file: str, password: str = None) -> bool:
        """
        导入密钥
        
        Args:
            input_file: 密钥文件路径
            password: 密码（如果密钥被加密）
            
        Returns:
            bool: 是否成功
        """
        try:
            with open(input_file, 'rb') as f:
                data = f.read()
            
            if password:
                # 使用密码解密密钥
                cipher = Fernet(self._derive_key_from_password(password))
                key = cipher.decrypt(data)
            else:
                key = data
            
            # 验证密钥有效性
            test_cipher = Fernet(key)
            test_data = test_cipher.encrypt(b'test')
            test_cipher.decrypt(test_data)
            
            # 更新密钥
            self.key = key
            self.cipher = Fernet(self.key)
            
            # 保存到密钥文件
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            return True
            
        except Exception as e:
            print(f"导入密钥失败: {str(e)}")
            return False


class SecureCookieManager:
    """安全的Cookies管理器（集成加密功能）"""
    
    def __init__(self, config_dir: str = "./config/accounts", password: str = None):
        """
        初始化安全Cookies管理器
        
        Args:
            config_dir: 配置目录
            password: 加密密码
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化加密工具
        key_file = self.config_dir.parent / '.key'
        self.encryption = Encryption(key_file=str(key_file), password=password)
    
    def save_account(self, account_name: str, cookies: list, metadata: Dict = None) -> bool:
        """
        保存加密的账号信息
        
        Args:
            account_name: 账号名称
            cookies: Cookies列表
            metadata: 元数据
            
        Returns:
            bool: 是否成功
        """
        try:
            # 构建账号数据
            account_data = {
                'account_name': account_name,
                'cookies': cookies,
                'metadata': metadata or {},
                'created_at': str(Path(__file__).stat().st_mtime),
            }
            
            # 加密整个数据
            encrypted_data = self.encryption.encrypt_dict(account_data)
            
            # 保存到文件
            file_path = self.config_dir / f"{account_name}.enc"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"保存账号失败: {str(e)}")
            return False
    
    def load_account(self, account_name: str) -> Optional[Dict]:
        """
        加载并解密账号信息
        
        Args:
            account_name: 账号名称
            
        Returns:
            Dict: 账号数据，失败返回None
        """
        try:
            file_path = self.config_dir / f"{account_name}.enc"
            
            if not file_path.exists():
                return None
            
            # 读取加密数据
            with open(file_path, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()
            
            # 解密
            account_data = self.encryption.decrypt_dict(encrypted_data)
            
            return account_data
            
        except Exception as e:
            print(f"加载账号失败: {str(e)}")
            return None
    
    def get_cookies(self, account_name: str) -> Optional[list]:
        """
        获取账号的Cookies
        
        Args:
            account_name: 账号名称
            
        Returns:
            list: Cookies列表
        """
        account_data = self.load_account(account_name)
        if account_data:
            return account_data.get('cookies', [])
        return None
