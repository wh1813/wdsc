"""
内容处理模块
负责内容的清洗、过滤、拼接、格式化等处理
"""
import re
from typing import List, Optional, Dict, Callable
from collections import Counter


class ContentProcessor:
    """内容处理器"""
    
    def __init__(self, config: dict, log_callback: Optional[Callable] = None):
        """
        初始化内容处理器
        
        Args:
            config: 配置字典
            log_callback: 日志回调函数
        """
        self.config = config
        self.log = log_callback if log_callback else print
        self.load_filter_rules()
    
    def load_filter_rules(self):
        """加载过滤规则"""
        keywords_text = self.config.get('filter_keywords', [])
        if isinstance(keywords_text, str):
            self.filter_keywords = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
        else:
            self.filter_keywords = keywords_text or []
        
        regex_text = self.config.get('filter_regex', [])
        if isinstance(regex_text, str):
            regex_list = [r.strip() for r in regex_text.split('\n') if r.strip()]
        else:
            regex_list = regex_text or []
        
        self.filter_patterns = []
        for pattern_str in regex_list:
            try:
                pattern = re.compile(pattern_str, re.MULTILINE)
                self.filter_patterns.append(pattern)
            except re.error as e:
                self.log("WARNING", f"正则表达式编译失败: {pattern_str} - {str(e)}")
        
        self.log("INFO", f"已加载过滤规则: {len(self.filter_keywords)} 个关键词, {len(self.filter_patterns)} 个正则")
    
    def process(self, content: str, title: str = None) -> Optional[str]:
        """
        完整的内容处理流程
        
        Args:
            content: 原始内容
            title: 文档标题（用于某些检测）
            
        Returns:
            str: 处理后的内容，如果内容无效返回None
        """
        if not content:
            self.log("ERROR", "内容为空")
            return None
        
        self.log("INFO", f"开始处理内容，原始长度: {len(content)} 字符")
        
        # 1. 基础清洗 (包含移除客套话和思考过程)
        content = self.basic_clean(content)
        
        # 2. 检测内容质量
        quality_check = self.check_quality(content)
        if not quality_check['is_valid']:
            self.log("ERROR", f"内容质量检测失败: {quality_check['reason']}")
            return None
        
        # 3. 关键词过滤
        content = self.filter_by_keywords(content)
        
        # 4. 正则过滤
        content = self.filter_by_regex(content)
        
        # 5. 最终清理
        content = self.final_clean(content)
        
        self.log("SUCCESS", f"内容处理完成，最终长度: {len(content)} 字符")
        
        return content
    
    def basic_clean(self, content: str) -> str:
        """
        基础清洗
        """
        content = content.strip()
        
        # 1. 清理开头的客套话
        conversational_starters = [
            r"^\s*[好的,当然,没问题,很乐意为您服务]+[.,，.。]?\s*",
            r"^\s*以下是为您生成的关于.*?的文章[：:]?\s*",
            r"^\s*为您生成了以下内容[：:]?\s*",
            r"^\s*根据您的要求，.*?文章如下[：:]?\s*",
        ]
        for pattern in conversational_starters:
            content = re.sub(pattern, '', content, count=1, flags=re.IGNORECASE)

        # 2. 清理思考过程或大纲
        thought_process_patterns = [
            r"^\s*\[思考过程[:：].*?\]\s*",            # 匹配 [思考过程：...]
            r"^\s*大纲[:：].*?\n(- .*?\n)*",        # 匹配以 "大纲：" 开头和后续的列表
            r"^\s*结构安排[:：].*?\n",               # 匹配 "结构安排："
            r"^\s*写作思路[:：].*?\n",               # 匹配 "写作思路："
        ]
        for pattern in thought_process_patterns:
             content = re.sub(pattern, '', content, count=1, flags=re.MULTILINE | re.IGNORECASE)

        # 3. 后续基础清理
        content = content.strip()
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        lines = content.split('\n')
        lines = [line.strip() for line in lines]
        content = '\n'.join(lines)
        
        return content.strip()

    def check_quality(self, content: str) -> Dict:
        """
        内容质量检测
        """
        result = {'is_valid': True, 'reason': ''}
        
        min_length = 50
        if len(content) < min_length:
            result['is_valid'] = False
            result['reason'] = f'内容过短（少于{min_length}字符）'
            return result
            
        error_keywords = ['error', '错误', 'failed', '失败', '异常', '超时', 'timeout', '网络错误']
        if any(keyword in content.lower() for keyword in error_keywords) and len(content) < 200:
            result['is_valid'] = False
            result['reason'] = '内容疑似错误提示'
            return result
        
        if self._has_excessive_repetition(content):
            result['is_valid'] = False
            result['reason'] = '检测到大量重复内容'
            return result
            
        return result

    def _has_excessive_repetition(self, content: str) -> bool:
        """检查是否有过多重复内容"""
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return False
        
        sentence_counts = Counter(sentences)
        max_count = max(sentence_counts.values()) if sentence_counts else 0
        
        return max_count > 3

    def filter_by_keywords(self, content: str) -> str:
        """按关键词过滤"""
        if not self.filter_keywords:
            return content
        
        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            if not any(keyword.lower() in line.lower() for keyword in self.filter_keywords):
                filtered_lines.append(line)
            else:
                self.log("INFO", f"因包含关键词而过滤行: {line[:50]}...")

        return '\n'.join(filtered_lines)
    
    def filter_by_regex(self, content: str) -> str:
        """按正则表达式过滤"""
        if not self.filter_patterns:
            return content
        
        original_length = len(content)
        for pattern in self.filter_patterns:
            content = pattern.sub('', content)
        
        if len(content) < original_length:
            self.log("INFO", f"通过正则表达式过滤移除了 {original_length - len(content)} 字符")
            
        return content
    
    def final_clean(self, content: str) -> str:
        """最终清理"""
        content = re.sub(r'\n{3,}', '\n\n', content).strip()
        
        # 清理结尾的客套话
        conversational_enders = [
            r"\n\s*希望以上内容对您有帮助.*$",
            r"\n\s*如果您还有其他问题.*$",
        ]
        for pattern in conversational_enders:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        content = content.strip()

        if content and not content.endswith(('.', '。', '!', '！', '?', '？', '\n')):
            content += '。'
            
        return content