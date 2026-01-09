"""
文件操作工具模块
提供便捷的文件和目录操作功能
"""
import os
import shutil
import hashlib
import tempfile
import zipfile
import json
from pathlib import Path
from typing import List, Optional, Union, Callable
from datetime import datetime
import re


class FileHelper:
    """文件操作辅助类"""
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]) -> Path:
        """
        确保目录存在，不存在则创建
        
        Args:
            path: 目录路径
            
        Returns:
            Path: 目录路径对象
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def safe_filename(filename: str, max_length: int = 255) -> str:
        """
        生成安全的文件名（移除非法字符）
        
        Args:
            filename: 原始文件名
            max_length: 最大长度
            
        Returns:
            str: 安全的文件名
        """
        # 移除Windows/Linux非法字符
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe_name = re.sub(illegal_chars, '_', filename)
        
        # 移除首尾空格和点
        safe_name = safe_name.strip('. ')
        
        # 限制长度
        if len(safe_name) > max_length:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[:max_length - len(ext)] + ext
        
        # 如果文件名为空，使用默认名称
        if not safe_name:
            safe_name = 'untitled'
        
        return safe_name
    
    @staticmethod
    def get_unique_filename(directory: Union[str, Path], filename: str) -> str:
        """
        获取唯一的文件名（避免覆盖）
        
        Args:
            directory: 目录路径
            filename: 文件名
            
        Returns:
            str: 唯一的文件名
        """
        directory = Path(directory)
        filepath = directory / filename
        
        if not filepath.exists():
            return filename
        
        # 分离文件名和扩展名
        name, ext = os.path.splitext(filename)
        
        # 添加序号
        counter = 1
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_filepath = directory / new_filename
            
            if not new_filepath.exists():
                return new_filename
            
            counter += 1
    
    @staticmethod
    def read_file(
        filepath: Union[str, Path],
        encoding: str = 'utf-8',
        errors: str = 'ignore'
    ) -> Optional[str]:
        """
        读取文本文件
        
        Args:
            filepath: 文件路径
            encoding: 编码格式
            errors: 错误处理方式
            
        Returns:
            str: 文件内容，失败返回None
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return None
            
            with open(filepath, 'r', encoding=encoding, errors=errors) as f:
                return f.read()
                
        except Exception as e:
            print(f"读取文件失败 {filepath}: {str(e)}")
            return None
    
    @staticmethod
    def read_lines(
        filepath: Union[str, Path],
        encoding: str = 'utf-8',
        strip: bool = True,
        skip_empty: bool = False
    ) -> Optional[List[str]]:
        """
        按行读取文本文件
        
        Args:
            filepath: 文件路径
            encoding: 编码格式
            strip: 是否去除首尾空白
            skip_empty: 是否跳过空行
            
        Returns:
            List[str]: 行列表，失败返回None
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return None
            
            with open(filepath, 'r', encoding=encoding) as f:
                lines = f.readlines()
            
            if strip:
                lines = [line.strip() for line in lines]
            
            if skip_empty:
                lines = [line for line in lines if line]
            
            return lines
            
        except Exception as e:
            print(f"读取文件失败 {filepath}: {str(e)}")
            return None
    
    @staticmethod
    def write_file(
        filepath: Union[str, Path],
        content: str,
        encoding: str = 'utf-8',
        append: bool = False
    ) -> bool:
        """
        写入文本文件
        
        Args:
            filepath: 文件路径
            content: 内容
            encoding: 编码格式
            append: 是否追加模式
            
        Returns:
            bool: 是否成功
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            
            with open(filepath, mode, encoding=encoding) as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"写入文件失败 {filepath}: {str(e)}")
            return False
    
    @staticmethod
    def write_lines(
        filepath: Union[str, Path],
        lines: List[str],
        encoding: str = 'utf-8',
        append: bool = False
    ) -> bool:
        """
        按行写入文本文件
        
        Args:
            filepath: 文件路径
            lines: 行列表
            encoding: 编码格式
            append: 是否追加模式
            
        Returns:
            bool: 是否成功
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            
            with open(filepath, mode, encoding=encoding) as f:
                for line in lines:
                    f.write(line)
                    if not line.endswith('\n'):
                        f.write('\n')
            
            return True
            
        except Exception as e:
            print(f"写入文件失败 {filepath}: {str(e)}")
            return False
    
    @staticmethod
    def read_json(filepath: Union[str, Path]) -> Optional[dict]:
        """
        读取JSON文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            dict: JSON内容，失败返回None
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"读取JSON文件失败 {filepath}: {str(e)}")
            return None
    
    @staticmethod
    def write_json(
        filepath: Union[str, Path],
        data: dict,
        indent: int = 2
    ) -> bool:
        """
        写入JSON文件
        
        Args:
            filepath: 文件路径
            data: 数据字典
            indent: 缩进空格数
            
        Returns:
            bool: 是否成功
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            
            return True
            
        except Exception as e:
            print(f"写入JSON文件失败 {filepath}: {str(e)}")
            return False
    
    @staticmethod
    def copy_file(
        src: Union[str, Path],
        dst: Union[str, Path],
        overwrite: bool = False
    ) -> bool:
        """
        复制文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            bool: 是否成功
        """
        try:
            src = Path(src)
            dst = Path(dst)
            
            if not src.exists():
                print(f"源文件不存在: {src}")
                return False
            
            if dst.exists() and not overwrite:
                print(f"目标文件已存在: {dst}")
                return False
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            
            return True
            
        except Exception as e:
            print(f"复制文件失败: {str(e)}")
            return False
    
    @staticmethod
    def move_file(
        src: Union[str, Path],
        dst: Union[str, Path],
        overwrite: bool = False
    ) -> bool:
        """
        移动文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            bool: 是否成功
        """
        try:
            src = Path(src)
            dst = Path(dst)
            
            if not src.exists():
                print(f"源文件不存在: {src}")
                return False
            
            if dst.exists() and not overwrite:
                print(f"目标文件已存在: {dst}")
                return False
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            
            return True
            
        except Exception as e:
            print(f"移动文件失败: {str(e)}")
            return False
    
    @staticmethod
    def delete_file(filepath: Union[str, Path]) -> bool:
        """
        删除文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            filepath = Path(filepath)
            
            if filepath.exists():
                filepath.unlink()
                return True
            
            return False
            
        except Exception as e:
            print(f"删除文件失败 {filepath}: {str(e)}")
            return False
    
    @staticmethod
    def delete_directory(
        dirpath: Union[str, Path],
        recursive: bool = True
    ) -> bool:
        """
        删除目录
        
        Args:
            dirpath: 目录路径
            recursive: 是否递归删除
            
        Returns:
            bool: 是否成功
        """
        try:
            dirpath = Path(dirpath)
            
            if not dirpath.exists():
                return False
            
            if recursive:
                shutil.rmtree(dirpath)
            else:
                dirpath.rmdir()
            
            return True
            
        except Exception as e:
            print(f"删除目录失败 {dirpath}: {str(e)}")
            return False
    
    @staticmethod
    def get_file_size(filepath: Union[str, Path]) -> int:
        """
        获取文件大小（字节）
        
        Args:
            filepath: 文件路径
            
        Returns:
            int: 文件大小，失败返回-1
        """
        try:
            filepath = Path(filepath)
            
            if filepath.exists() and filepath.is_file():
                return filepath.stat().st_size
            
            return -1
            
        except Exception as e:
            print(f"获取文件大小失败 {filepath}: {str(e)}")
            return -1
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节数
            
        Returns:
            str: 格式化后的大小（如 1.5 MB）
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def get_directory_size(dirpath: Union[str, Path]) -> int:
        """
        获取目录总大小（递归）
        
        Args:
            dirpath: 目录路径
            
        Returns:
            int: 总大小（字节）
        """
        try:
            dirpath = Path(dirpath)
            total_size = 0
            
            if dirpath.is_file():
                return dirpath.stat().st_size
            
            for item in dirpath.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
            
            return total_size
            
        except Exception as e:
            print(f"获取目录大小失败 {dirpath}: {str(e)}")
            return 0
    
    @staticmethod
    def find_files(
        directory: Union[str, Path],
        pattern: str = '*',
        recursive: bool = True
    ) -> List[Path]:
        """
        查找文件
        
        Args:
            directory: 目录路径
            pattern: 文件模式（支持通配符）
            recursive: 是否递归搜索
            
        Returns:
            List[Path]: 文件路径列表
        """
        try:
            directory = Path(directory)
            
            if not directory.exists():
                return []
            
            if recursive:
                return list(directory.rglob(pattern))
            else:
                return list(directory.glob(pattern))
                
        except Exception as e:
            print(f"查找文件失败 {directory}: {str(e)}")
            return []
    
    @staticmethod
    def filter_files(
        files: List[Path],
        extensions: List[str] = None,
        min_size: int = None,
        max_size: int = None,
        modified_after: datetime = None,
        modified_before: datetime = None
    ) -> List[Path]:
        """
        过滤文件列表
        
        Args:
            files: 文件路径列表
            extensions: 扩展名列表（如 ['.txt', '.doc']）
            min_size: 最小文件大小（字节）
            max_size: 最大文件大小（字节）
            modified_after: 修改时间晚于
            modified_before: 修改时间早于
            
        Returns:
            List[Path]: 过滤后的文件列表
        """
        filtered = []
        
        for file in files:
            if not file.is_file():
                continue
            
            # 扩展名过滤
            if extensions:
                if file.suffix.lower() not in [ext.lower() for ext in extensions]:
                    continue
            
            # 文件大小过滤
            if min_size is not None or max_size is not None:
                size = file.stat().st_size
                
                if min_size is not None and size < min_size:
                    continue
                
                if max_size is not None and size > max_size:
                    continue
            
            # 修改时间过滤
            if modified_after or modified_before:
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                
                if modified_after and mtime < modified_after:
                    continue
                
                if modified_before and mtime > modified_before:
                    continue
            
            filtered.append(file)
        
        return filtered
    
    @staticmethod
    def calculate_hash(
        filepath: Union[str, Path],
        algorithm: str = 'md5'
    ) -> Optional[str]:
        """
        计算文件哈希值
        
        Args:
            filepath: 文件路径
            algorithm: 哈希算法（md5, sha1, sha256）
            
        Returns:
            str: 哈希值，失败返回None
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return None
            
            # 选择哈希算法
            if algorithm == 'md5':
                hash_obj = hashlib.md5()
            elif algorithm == 'sha1':
                hash_obj = hashlib.sha1()
            elif algorithm == 'sha256':
                hash_obj = hashlib.sha256()
            else:
                raise ValueError(f"不支持的哈希算法: {algorithm}")
            
            # 分块读取文件计算哈希
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            print(f"计算哈希值失败 {filepath}: {str(e)}")
            return None
    
    @staticmethod
    def create_zip(
        output_file: Union[str, Path],
        source_files: List[Union[str, Path]],
        base_dir: Union[str, Path] = None
    ) -> bool:
        """
        创建ZIP压缩文件
        
        Args:
            output_file: 输出ZIP文件路径
            source_files: 要压缩的文件列表
            base_dir: 基础目录（用于保持相对路径）
            
        Returns:
            bool: 是否成功
        """
        try:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in source_files:
                    file = Path(file)
                    
                    if not file.exists():
                        continue
                    
                    # 计算在ZIP中的路径
                    if base_dir:
                        arcname = file.relative_to(base_dir)
                    else:
                        arcname = file.name
                    
                    if file.is_file():
                        zipf.write(file, arcname)
                    elif file.is_dir():
                        for item in file.rglob('*'):
                            if item.is_file():
                                if base_dir:
                                    item_arcname = item.relative_to(base_dir)
                                else:
                                    item_arcname = item.relative_to(file.parent)
                                zipf.write(item, item_arcname)
            
            return True
            
        except Exception as e:
            print(f"创建ZIP文件失败: {str(e)}")
            return False
    
    @staticmethod
    def extract_zip(
        zip_file: Union[str, Path],
        output_dir: Union[str, Path]
    ) -> bool:
        """
        解压ZIP文件
        
        Args:
            zip_file: ZIP文件路径
            output_dir: 解压目录
            
        Returns:
            bool: 是否成功
        """
        try:
            zip_file = Path(zip_file)
            output_dir = Path(output_dir)
            
            if not zip_file.exists():
                print(f"ZIP文件不存在: {zip_file}")
                return False
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_file, 'r') as zipf:
                zipf.extractall(output_dir)
            
            return True
            
        except Exception as e:
            print(f"解压ZIP文件失败: {str(e)}")
            return False
    
    @staticmethod
    def create_temp_file(
        suffix: str = '',
        prefix: str = 'tmp',
        dir: Union[str, Path] = None,
        text: bool = True
    ) -> str:
        """
        创建临时文件
        
        Args:
            suffix: 文件后缀
            prefix: 文件前缀
            dir: 临时目录
            text: 是否文本模式
            
        Returns:
            str: 临时文件路径
        """
        fd, path = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=str(dir) if dir else None,
            text=text
        )
        
        os.close(fd)
        return path
    
    @staticmethod
    def create_temp_directory(
        suffix: str = '',
        prefix: str = 'tmp',
        dir: Union[str, Path] = None
    ) -> str:
        """
        创建临时目录
        
        Args:
            suffix: 目录后缀
            prefix: 目录前缀
            dir: 父目录
            
        Returns:
            str: 临时目录路径
        """
        return tempfile.mkdtemp(
            suffix=suffix,
            prefix=prefix,
            dir=str(dir) if dir else None
        )
    
    @staticmethod
    def batch_rename(
        directory: Union[str, Path],
        pattern: str = '*',
        rename_func: Callable[[str], str] = None,
        dry_run: bool = False
    ) -> List[tuple]:
        """
        批量重命名文件
        
        Args:
            directory: 目录路径
            pattern: 文件模式
            rename_func: 重命名函数（接收旧文件名，返回新文件名）
            dry_run: 是否只是预览（不实际执行）
            
        Returns:
            List[tuple]: (原文件名, 新文件名) 列表
        """
        directory = Path(directory)
        renamed_files = []
        
        if not rename_func:
            return renamed_files
        
        for file in directory.glob(pattern):
            if not file.is_file():
                continue
            
            old_name = file.name
            new_name = rename_func(old_name)
            
            if old_name == new_name:
                continue
            
            new_path = file.parent / new_name
            
            renamed_files.append((old_name, new_name))
            
            if not dry_run:
                try:
                    file.rename(new_path)
                except Exception as e:
                    print(f"重命名失败 {old_name} -> {new_name}: {str(e)}")
        
        return renamed_files
    
    @staticmethod
    def get_file_extension(filepath: Union[str, Path]) -> str:
        """获取文件扩展名（不含点）"""
        return Path(filepath).suffix.lstrip('.')
    
    @staticmethod
    def change_extension(
        filepath: Union[str, Path],
        new_ext: str
    ) -> Path:
        """
        更改文件扩展名
        
        Args:
            filepath: 文件路径
            new_ext: 新扩展名
            
        Returns:
            Path: 新文件路径
        """
        filepath = Path(filepath)
        
        if not new_ext.startswith('.'):
            new_ext = '.' + new_ext
        
        return filepath.with_suffix(new_ext)


# 便捷函数
def ensure_dir(path: Union[str, Path]) -> Path:
    """确保目录存在"""
    return FileHelper.ensure_dir(path)


def safe_filename(filename: str) -> str:
    """生成安全的文件名"""
    return FileHelper.safe_filename(filename)


def read_file(filepath: Union[str, Path], **kwargs) -> Optional[str]:
    """读取文本文件"""
    return FileHelper.read_file(filepath, **kwargs)


def write_file(filepath: Union[str, Path], content: str, **kwargs) -> bool:
    """写入文本文件"""
    return FileHelper.write_file(filepath, content, **kwargs)


def read_json(filepath: Union[str, Path]) -> Optional[dict]:
    """读取JSON文件"""
    return FileHelper.read_json(filepath)


def write_json(filepath: Union[str, Path], data: dict, **kwargs) -> bool:
    """写入JSON文件"""
    return FileHelper.write_json(filepath, data, **kwargs)
