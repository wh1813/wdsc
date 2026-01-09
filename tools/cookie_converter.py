"""
Cookie格式转换工具
将浏览器Cookie字符串转换为JSON格式
"""
import json
from urllib.parse import urlparse


def parse_cookie_string(cookie_string: str, domain: str = None, url: str = None) -> list:
    """
    解析Cookie字符串为JSON格式
    
    Args:
        cookie_string: Cookie字符串（从F12复制的）
        domain: 目标域名（如 .achuanai.cn）
        url: 完整URL（用于自动提取域名）
    
    Returns:
        list: Cookie JSON数组
    """
    # 自动提取域名
    if url and not domain:
        parsed = urlparse(url)
        domain = f".{parsed.netloc}"
    
    if not domain:
        domain = ".example.com"  # 默认域名
    
    cookies = []
    
    # 分割Cookie字符串
    cookie_pairs = cookie_string.split(';')
    
    for pair in cookie_pairs:
        pair = pair.strip()
        
        if not pair or '=' not in pair:
            continue
        
        # 分离name和value
        name, value = pair.split('=', 1)
        name = name.strip()
        value = value.strip()
        
        # 构建Cookie对象
        cookie = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": "/",
            "secure": True,
            "httpOnly": False
        }
        
        cookies.append(cookie)
    
    return cookies


def format_cookies_json(cookies: list, indent: int = 2) -> str:
    """格式化Cookie为JSON字符串"""
    return json.dumps(cookies, ensure_ascii=False, indent=indent)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("Cookie格式转换工具")
    print("=" * 60)
    
    # 方式1: 从命令行输入
    print("\n请粘贴从浏览器F12复制的Cookie字符串:")
    print("(格式: name1=value1; name2=value2; ...)")
    print("-" * 60)
    
    cookie_string = input("Cookie字符串: ").strip()
    
    if not cookie_string:
        # 使用示例Cookie
        cookie_string = "https_waf_cookie=da7a93e8-3fba-4490bfb22dc197a77a42d6194d0804988ec2; colorMode=light"
        print(f"\n使用示例Cookie: {cookie_string}")
    
    url = input("目标网站URL (如 https://ai.achuanai.cn): ").strip()
    
    if not url:
        url = "https://ai.achuanai.cn"
        print(f"使用默认URL: {url}")
    
    # 转换
    cookies = parse_cookie_string(cookie_string, url=url)
    
    # 输出JSON
    json_str = format_cookies_json(cookies)
    
    print("\n" + "=" * 60)
    print("转换后的Cookie JSON:")
    print("=" * 60)
    print(json_str)
    print("=" * 60)
    print("\n✓ 请复制上面的JSON，粘贴到UI界面的Cookie输入框中")
    print("  然后点击'保存'按钮")
