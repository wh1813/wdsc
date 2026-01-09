"""
Web自动化模块
负责浏览器控制、页面操作、模型切换等核心功能
"""
import asyncio
import json
from typing import Optional, List, Dict, Callable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
from datetime import datetime
import re


class WebAutomation:
    """Web自动化核心类"""
    
    def __init__(self, config: dict, log_callback: Optional[Callable] = None):
        """
        初始化Web自动化
        
        Args:
            config: 配置字典
            log_callback: 日志回调函数
        """
        self.config = config
        self.log = log_callback if log_callback else print
        
        # Playwright对象
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # 状态变量
        self.is_initialized = False
        self.current_model = None
        
        # 从配置读取选择器
        self.selectors = config.get('web_elements', {})
        self.model_mapping = config.get('model_mapping', {})
        
    async def initialize(self, cookies: List[Dict] = None) -> bool:
        """
        初始化浏览器
        
        Args:
            cookies: Cookies列表
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.log("INFO", "正在启动浏览器...")
            
            # 启动Playwright
            self.playwright = await async_playwright().start()
            
            # 浏览器配置
            headless = not self.config.get('settings', {}).get('show_browser', False)
            
            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            self.log("SUCCESS", "浏览器启动成功")
            
            # 创建上下文
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # 注入Cookies
            if cookies:
                await self.context.add_cookies(cookies)
                self.log("SUCCESS", f"已注入 {len(cookies)} 个Cookies")
            
            # 创建页面
            self.page = await self.context.new_page()
            
            # 设置超时
            timeout = self.config.get('settings', {}).get('timeout', 300) * 1000
            self.page.set_default_timeout(timeout)
            
            self.is_initialized = True
            self.log("SUCCESS", "浏览器初始化完成")
            
            return True
            
        except Exception as e:
            self.log("ERROR", f"浏览器初始化失败: {str(e)}")
            return False
    
    async def navigate_to_site(self, url: str) -> bool:
        """
        导航到指定网站
        
        Args:
            url: 目标URL
            
        Returns:
            bool: 导航是否成功
        """
        try:
            self.log("INFO", f"正在访问网站: {url}")
            
            await self.page.goto(url, wait_until='networkidle')
            
            # 等待页面完全加载
            await asyncio.sleep(2)
            
            self.log("SUCCESS", "网站访问成功")
            return True
            
        except Exception as e:
            self.log("ERROR", f"访问网站失败: {str(e)}")
            return False
    
    async def verify_login(self) -> bool:
        """
        验证登录状态
        
        Returns:
            bool: 是否已登录
        """
        try:
            # 检查是否存在登录按钮（如果存在说明未登录）
            login_button = await self.page.query_selector('button:has-text("登录"), a:has-text("登录")')
            
            if login_button:
                self.log("WARNING", "检测到未登录，Cookies可能已失效")
                return False
            
            # 检查是否能找到对话界面元素
            input_selector = self.selectors.get('input', 'textarea')
            input_element = await self.page.query_selector(input_selector)
            
            if input_element:
                self.log("SUCCESS", "登录状态验证成功")
                return True
            else:
                self.log("WARNING", "未找到输入框，可能未登录")
                return False
                
        except Exception as e:
            self.log("ERROR", f"验证登录状态失败: {str(e)}")
            return False
    
    async def switch_model(self, model_name: str) -> bool:
        """
        切换AI模型
        
        Args:
            model_name: 软件中的模型名称（会自动映射到网页名称）
            
        Returns:
            bool: 切换是否成功
        """
        try:
            # 映射模型名称
            web_model_name = self.model_mapping.get(model_name, model_name)
            self.log("INFO", f"准备切换模型: {model_name} → {web_model_name}")
            
            # 1. 点击模型选择按钮
            button_selector = self.selectors.get('model_button', 'button.model-selector')
            
            try:
                await self.page.click(button_selector, timeout=5000)
                self.log("INFO", "已点击模型选择按钮")
            except:
                # 如果找不到按钮，尝试其他常见选择器
                alternative_selectors = [
                    'button:has-text("模型")',
                    '.model-selector',
                    '[class*="model"]',
                ]
                
                for selector in alternative_selectors:
                    try:
                        await self.page.click(selector, timeout=3000)
                        self.log("INFO", f"使用备选选择器点击成功: {selector}")
                        break
                    except:
                        continue
                else:
                    raise Exception("无法找到模型选择按钮")
            
            # 2. 等待下拉菜单出现
            menu_selector = self.selectors.get('menu', '.n-base-select-menu')
            await self.page.wait_for_selector(menu_selector, timeout=5000)
            self.log("INFO", "下拉菜单已出现")
            
            # 3. 查找并点击目标模型
            option_selector = self.selectors.get('option', '.n-base-select-option')
            
            # 使用文本匹配策略
            target_selector = f'{option_selector}:has-text("{web_model_name}")'
            
            # 等待选项可见
            await self.page.wait_for_selector(target_selector, timeout=5000)
            
            # 点击选项
            await self.page.click(target_selector)
            self.log("SUCCESS", f"已点击模型选项: {web_model_name}")
            
            # 4. 等待UI更新
            await asyncio.sleep(1.5)
            
            # 5. 验证切换成功
            selected_selector = f'.n-base-select-option--selected:has-text("{web_model_name}")'
            selected = await self.page.query_selector(selected_selector)
            
            if selected:
                self.current_model = model_name
                self.log("SUCCESS", f"✓ 模型切换成功: {web_model_name}")
                return True
            else:
                self.log("WARNING", "模型切换可能失败，未检测到选中状态")
                # 即使未检测到选中状态，也假设切换成功（某些网站不显示选中状态）
                self.current_model = model_name
                return True
                
        except Exception as e:
            self.log("ERROR", f"模型切换失败: {str(e)}")
            return False
    
    async def send_message(self, message: str, wait_for_response: bool = True) -> bool:
        """
        发送消息
        
        Args:
            message: 要发送的消息
            wait_for_response: 是否等待响应开始
            
        Returns:
            bool: 发送是否成功
        """
        try:
            self.log("INFO", f"正在发送消息: {message[:50]}...")
            
            # 1. 定位输入框
            input_selector = self.selectors.get('input', 'textarea')
            
            # 清空输入框
            await self.page.fill(input_selector, '')
            await asyncio.sleep(0.5)
            
            # 2. 输入消息
            await self.page.fill(input_selector, message)
            await asyncio.sleep(0.5)
            
            # 3. 点击发送按钮
            send_selector = self.selectors.get('send_button', 'button[type="submit"]')
            
            try:
                await self.page.click(send_selector, timeout=3000)
            except:
                # 如果找不到发送按钮，尝试按Enter键
                await self.page.press(input_selector, 'Enter')
            
            self.log("SUCCESS", "消息已发送")
            
            # 4. 等待响应开始（可选）
            if wait_for_response:
                await asyncio.sleep(2)
                self.log("INFO", "等待模型响应...")
            
            return True
            
        except Exception as e:
            self.log("ERROR", f"发送消息失败: {str(e)}")
            return False
    
    async def wait_for_response_complete(self, timeout: int = 300) -> bool:
        """
        等待模型响应完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功等待到响应完成
        """
        try:
            self.log("INFO", "等待响应完成...")
            
            start_time = asyncio.get_event_loop().time()
            check_interval = 2  # 每2秒检查一次
            
            while True:
                # 检查是否超时
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    self.log("ERROR", f"等待响应超时 ({timeout}秒)")
                    return False
                
                # 检查响应是否完成的多种方式
                is_complete = await self._check_response_complete()
                
                if is_complete:
                    self.log("SUCCESS", "响应已完成")
                    return True
                
                # 检查是否有错误提示
                has_error = await self._check_error_message()
                if has_error:
                    self.log("ERROR", "检测到错误提示")
                    return False
                
                # 检查是否需要继续（截断情况）
                needs_continue = await self._check_needs_continue()
                if needs_continue:
                    self.log("WARNING", "检测到内容截断，准备继续...")
                    await self._click_continue()
                    await asyncio.sleep(2)
                    continue
                
                # 等待后继续检查
                await asyncio.sleep(check_interval)
                
        except Exception as e:
            self.log("ERROR", f"等待响应时出错: {str(e)}")
            return False
    
    async def _check_response_complete(self) -> bool:
        """
        检查响应是否完成
        
        Returns:
            bool: 是否完成
        """
        try:
            # 方法1: 检查输入框是否可用（生成完成后解锁）
            input_selector = self.selectors.get('input', 'textarea')
            input_element = await self.page.query_selector(input_selector)
            
            if input_element:
                is_disabled = await input_element.get_attribute('disabled')
                is_readonly = await input_element.get_attribute('readonly')
                
                if not is_disabled and not is_readonly:
                    # 输入框已启用，可能完成了
                    await asyncio.sleep(1)  # 再等1秒确认
                    return True
            
            # 方法2: 检查是否有"正在生成"的加载动画
            loading_selectors = [
                '.loading',
                '.generating',
                '[class*="loading"]',
                '.n-spin',
            ]
            
            for selector in loading_selectors:
                loading = await self.page.query_selector(selector)
                if loading:
                    is_visible = await loading.is_visible()
                    if is_visible:
                        return False  # 还在加载中
            
            # 方法3: 检查复制按钮是否可点击
            copy_selector = self.selectors.get('copy_button')
            if copy_selector:
                copy_button = await self.page.query_selector(copy_selector)
                if copy_button:
                    is_enabled = await copy_button.is_enabled()
                    if is_enabled:
                        return True
            
            # 默认认为未完成
            return False
            
        except Exception as e:
            self.log("WARNING", f"检查响应完成状态时出错: {str(e)}")
            return False
    
    async def _check_error_message(self) -> bool:
        """
        检查是否有错误消息
        
        Returns:
            bool: 是否有错误
        """
        try:
            # 常见错误提示关键词
            error_keywords = [
                '错误',
                '失败',
                'error',
                'failed',
                '超时',
                'timeout',
                '网络异常',
                '请稍后再试',
                '系统繁忙',
                '达到限制',
            ]
            
            # 获取页面文本
            page_text = await self.page.inner_text('body')
            
            # 检查是否包含错误关键词
            for keyword in error_keywords:
                if keyword.lower() in page_text.lower():
                    self.log("WARNING", f"检测到错误关键词: {keyword}")
                    return True
            
            # 检查错误消息框
            error_selectors = [
                '.error-message',
                '.alert-error',
                '[class*="error"]',
                '.n-message--error',
            ]
            
            for selector in error_selectors:
                error_element = await self.page.query_selector(selector)
                if error_element:
                    is_visible = await error_element.is_visible()
                    if is_visible:
                        error_text = await error_element.inner_text()
                        self.log("ERROR", f"发现错误消息: {error_text}")
                        return True
            
            return False
            
        except Exception as e:
            self.log("WARNING", f"检查错误消息时出错: {str(e)}")
            return False
    
    async def _check_needs_continue(self) -> bool:
        """
        检查是否需要继续（内容截断）
        
        Returns:
            bool: 是否需要继续
        """
        try:
            # 查找"继续"按钮
            continue_selectors = [
                'button:has-text("继续")',
                'button:has-text("Continue")',
                'button:has-text("continue")',
                '.continue-button',
                '[class*="continue"]',
            ]
            
            for selector in continue_selectors:
                button = await self.page.query_selector(selector)
                if button:
                    is_visible = await button.is_visible()
                    if is_visible:
                        self.log("INFO", "发现继续按钮")
                        return True
            
            # 检查内容中是否有截断提示
            page_text = await self.page.inner_text('body')
            truncate_keywords = [
                '内容过长',
                '已截断',
                '继续输出',
                'truncated',
                'click to continue',
            ]
            
            for keyword in truncate_keywords:
                if keyword.lower() in page_text.lower():
                    self.log("INFO", f"检测到截断提示: {keyword}")
                    return True
            
            return False
            
        except Exception as e:
            self.log("WARNING", f"检查是否需要继续时出错: {str(e)}")
            return False
    
    async def _click_continue(self) -> bool:
        """
        点击继续按钮
        
        Returns:
            bool: 是否成功点击
        """
        try:
            continue_selectors = [
                'button:has-text("继续")',
                'button:has-text("Continue")',
                'button:has-text("continue")',
                '.continue-button',
            ]
            
            for selector in continue_selectors:
                try:
                    await self.page.click(selector, timeout=2000)
                    self.log("SUCCESS", "已点击继续按钮")
                    return True
                except:
                    continue
            
            # 如果没找到按钮，尝试发送空消息触发继续
            self.log("WARNING", "未找到继续按钮，尝试发送空消息")
            await self.send_message("继续", wait_for_response=True)
            return True
            
        except Exception as e:
            self.log("ERROR", f"点击继续按钮失败: {str(e)}")
            return False
    
    async def get_response_content(self) -> Optional[str]:
        """
        获取响应内容
        
        Returns:
            str: 响应内容，失败返回None
        """
        try:
            self.log("INFO", "正在提取响应内容...")
            
            # 方法1: 通过复制按钮复制内容
            copy_selector = self.selectors.get('copy_button')
            if copy_selector:
                try:
                    # 点击复制按钮
                    await self.page.click(copy_selector, timeout=3000)
                    await asyncio.sleep(0.5)
                    
                    # 从剪贴板读取
                    # 注意: Playwright在headless模式下无法直接读取剪贴板
                    # 这里需要使用其他方法
                    self.log("INFO", "已点击复制按钮")
                except Exception as e:
                    self.log("WARNING", f"复制按钮点击失败: {str(e)}")
            
            # 方法2: 直接提取最后一条消息的内容
            # 常见的消息容器选择器
            message_selectors = [
                '.message-content:last-child',
                '.chat-message:last-child',
                '.response-content:last-child',
                '[class*="message"]:last-child',
                '[class*="response"]:last-child',
            ]
            
            content = None
            for selector in message_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        content = await element.inner_text()
                        if content and len(content) > 10:
                            break
                except:
                    continue
            
            if not content:
                # 方法3: 尝试提取整个对话区域的最后部分
                try:
                    all_messages = await self.page.query_selector_all('[class*="message"]')
                    if all_messages:
                        last_message = all_messages[-1]
                        content = await last_message.inner_text()
                except:
                    pass
            
            if content:
                self.log("SUCCESS", f"成功提取内容，长度: {len(content)} 字符")
                return content
            else:
                self.log("ERROR", "未能提取到响应内容")
                return None
                
        except Exception as e:
            self.log("ERROR", f"获取响应内容失败: {str(e)}")
            return None
    
    async def get_response_content_by_copy(self) -> Optional[str]:
        """
        通过模拟Ctrl+A和Ctrl+C来获取内容
        
        Returns:
            str: 响应内容
        """
        try:
            # 先点击到对话区域
            await self.page.click('body')
            
            # 执行JavaScript来获取最后一条消息
            content = await self.page.evaluate("""
                () => {
                    // 尝试多种选择器
                    const selectors = [
                        '.message-content',
                        '.chat-message',
                        '.response-content',
                        '[class*="message"]',
                    ];
                    
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            const lastElement = elements[elements.length - 1];
                            return lastElement.innerText || lastElement.textContent;
                        }
                    }
                    
                    return null;
                }
            """)
            
            return content
            
        except Exception as e:
            self.log("ERROR", f"通过JavaScript获取内容失败: {str(e)}")
            return None
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            self.is_initialized = False
            self.log("INFO", "浏览器已关闭")
            
        except Exception as e:
            self.log("ERROR", f"关闭浏览器时出错: {str(e)}")
    
    async def take_screenshot(self, path: str):
        """截图保存"""
        try:
            if self.page:
                await self.page.screenshot(path=path, full_page=True)
                self.log("SUCCESS", f"截图已保存: {path}")
        except Exception as e:
            self.log("ERROR", f"截图失败: {str(e)}")
    
    def __del__(self):
        """析构函数"""
        if self.is_initialized:
            try:
                asyncio.get_event_loop().run_until_complete(self.close())
            except:
                pass
