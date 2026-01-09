"""
浏览器控制器 - 最终修复版 (优化复制超时和健壮性)
"""
import asyncio
import time # 导入 time 模块用于整体超时
from typing import Optional, Callable, List, Dict
from playwright.async_api import (
    async_playwright, Page, Browser, BrowserContext,
    TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
)
import traceback

AI_MESSAGE_CONTAINER_CLASS = "aa-html-content"

class BrowserController:
    """负责与网页进行交互的控制器"""

    def __init__(self, config: dict, log_callback: Optional[Callable] = None):
        self.config = config
        self.log_callback = log_callback
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def log(self, level: str, message: str):
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    async def initialize(self, cookies=None, headless=True) -> bool:
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled", "--start-maximized"],
            )
            self.context = await self.browser.new_context(viewport=None)
            # 设置默认操作超时，例如点击、填充等
            self.context.set_default_timeout(30000) # 30秒默认操作超时
            self.page = await self.context.new_page()

            start_url = self.config.get("website_url", "https://ai.achuanai.cn/")
            # 设置页面加载超时
            await self.page.goto(start_url, wait_until='domcontentloaded', timeout=60000) # 60秒页面加载
            self.log("INFO", f"打开页面: {start_url}")
            if cookies: await self.context.add_cookies(cookies)
            await asyncio.sleep(3)
            await self.handle_overlays()
            self.log("SUCCESS", "BrowserController 初始化完成")
            return True
        except Exception as e:
            self.log("ERROR", f"Browser 初始化失败: {str(e)}\n{traceback.format_exc()}")
            return False

    async def handle_overlays(self):
        overlay_selectors = [
            "button:has-text('我知道了')", "button:has-text('同意')", "button:has-text('接受')",
            "div[class*='close']", "button[class*='close']", "i[class*='close']",
            "[aria-label*='close' i]", "[aria-label*='关闭' i]",
            "div[role='dialog'] button:has-text('Close')", "div[role='dialog'] button:has-text('关闭')",
        ]
        closed_overlay = False
        for selector in overlay_selectors:
            try:
                button = self.page.locator(selector).first
                if await button.is_visible(timeout=1000): # 快速检查
                    await button.click(timeout=2000) # 快速点击
                    self.log("INFO", f"已自动关闭一个弹窗/悬浮窗 (选择器: {selector})")
                    closed_overlay = True
                    await asyncio.sleep(1.0) # 关闭后稍等
            except (PlaywrightTimeoutError, PlaywrightError):
                 pass
        # if closed_overlay: await asyncio.sleep(0.5)

    async def create_new_conversation(self):
        try:
            new_chat_button = self.page.locator("a:has-text('新对话'), button:has-text('New chat'), button:has-text('新建聊天'), button[aria-label*='New chat' i]").first
            await new_chat_button.wait_for(state='visible', timeout=5000)
            await new_chat_button.click(timeout=5000)
            self.log("INFO", "已创建新对话。")
            await asyncio.sleep(1.5)
            await self.handle_overlays()
        except PlaywrightTimeoutError:
            self.log("DEBUG", "未找到明确的新对话按钮，将继续在当前对话操作。")
        except Exception as e:
            self.log("WARNING", f"尝试创建新对话时发生错误: {str(e)}")

    async def select_model(self, model_name: str):
        """跳过模型选择功能"""
        self.log("INFO", f"模型选择功能已跳过 (请求选择的模型: {model_name})。将使用页面默认模型。")
        await asyncio.sleep(0.1)

    async def send_message(self, message: str, system_prompt: Optional[str] = None) -> bool:
        try:
            await self.handle_overlays()

            input_selector = "textarea"
            try:
                await self.page.wait_for_selector(input_selector, state='visible', timeout=20000)
            except PlaywrightTimeoutError:
                self.log("ERROR", "等待输入框可见超时！")
                await self.refresh_page(); return False

            input_box = self.page.locator(input_selector).first

            # 等待输入框可用 (使用 is_enabled 配合循环检查，替代有问题的 wait_for)
            try:
                 start_wait = time.time()
                 while not await input_box.is_enabled(timeout=1000): # 每次检查1秒
                      if time.time() - start_wait > 20: # 总等待20秒
                           raise PlaywrightTimeoutError("等待输入框变为 enabled 状态超时 (20秒)")
                      self.log("DEBUG", "输入框当前不可用，等待1秒...")
                      await asyncio.sleep(1)
                 self.log("DEBUG", "输入框已变为可编辑 (enabled) 状态。")
            except PlaywrightTimeoutError as e:
                 self.log("ERROR", str(e))
                 await self.refresh_page(); return False

            self.log("DEBUG", "正在强制清空和聚焦输入框...")
            try:
                await input_box.evaluate("node => node.value = ''")
                await input_box.focus()
                await input_box.fill("", timeout=5000)
            except Exception as clear_err:
                 self.log("WARNING", f"清空输入框时出错: {clear_err}, 继续...")

            full_message = f"{system_prompt.strip()}\n\n{message}" if system_prompt and system_prompt.strip() else message
            try:
                await input_box.fill(full_message, timeout=15000)
            except Exception as fill_err:
                 self.log("ERROR", f"填充输入框时出错: {fill_err}")
                 await self.refresh_page(); return False

            self.log("INFO", f"已输入消息 (前50字符): {message[:50]}...")
            await asyncio.sleep(0.8)

            send_button_selector = "button:has-text('发送'), button[aria-label*='Send'], button[class*='send']"
            send_button = self.page.locator(send_button_selector).last
            send_success = False
            try:
                 # Click 会自动等待 enabled
                 await send_button.scroll_into_view_if_needed(timeout=5000)
                 await asyncio.sleep(0.3)
                 await send_button.click(timeout=10000)
                 self.log("INFO", "已点击发送按钮。")
                 send_success = True
            except Exception:
                 self.log("WARNING", "发送按钮点击/超时，尝试Enter键...")
                 try:
                      await input_box.press("Enter")
                      self.log("INFO", "通过Enter键发送。")
                      send_success = True
                 except Exception as enter_err:
                      self.log("ERROR", f"Enter键发送也失败: {enter_err}")

            await asyncio.sleep(3.0) # 增加验证前等待
            input_value_after = ""
            is_disabled_after = False
            try:
                input_value_after = await input_box.input_value(timeout=5000)
                is_disabled_after = await input_box.is_disabled(timeout=5000)
            except PlaywrightTimeoutError:
                 self.log("WARNING", "发送后验证超时，假设发送成功。")
                 return True # 乐观返回

            if send_success and not is_disabled_after and input_value_after.strip() == full_message.strip():
                self.log("ERROR", "发送验证失败！输入框未清空且未禁用。")
                await self.refresh_page(); return False
            elif not send_success:
                 self.log("ERROR", "未能通过按钮或Enter键发送。")
                 return False

            self.log("SUCCESS", "消息发送成功并通过验证。")
            return True

        except Exception as e:
            self.log("ERROR", f"发送消息过程中发生严重错误: {str(e)}\n{traceback.format_exc()}")
            return False

    async def refresh_page(self):
        try:
            self.log("INFO", "正在刷新页面...")
            await self.page.reload(wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)
            self.log("SUCCESS", "页面刷新完成。")
            await self.handle_overlays()
            try:
                 await self.page.locator("textarea").first.wait_for(state='visible', timeout=15000)
                 self.log("DEBUG", "刷新后输入框可见。")
            except PlaywrightTimeoutError:
                 self.log("WARNING", "刷新后输入框在15秒内未变为可见状态。")
            return True
        except Exception as e:
            self.log("ERROR", f"刷新页面时发生严重错误: {str(e)}")
            try:
                 start_url = self.config.get("website_url", "https://ai.achuanai.cn/")
                 await self.page.goto(start_url, wait_until='domcontentloaded', timeout=60000)
                 self.log("INFO", f"刷新失败后，已重新导航到主页: {start_url}")
                 await asyncio.sleep(3); await self.handle_overlays(); return True
            except Exception as goto_err:
                 self.log("CRITICAL", f"刷新和重新导航均失败: {goto_err}\n{traceback.format_exc()}"); return False

    async def wait_for_response(self, timeout: int = 300) -> bool:
        self.log("INFO", "等待 AI 响应稳定...")
        start_time = asyncio.get_event_loop().time()
        response_block_selector = f"div.{AI_MESSAGE_CONTAINER_CLASS}"
        last_content_length = -1
        stable_count = 0
        STABLE_THRESHOLD = 4

        try:
            await self.page.wait_for_selector(response_block_selector, state='attached', timeout=60000)
            self.log("DEBUG", "AI回复容器已出现。")
        except Exception as e:
             self.log("ERROR", f"等待AI响应容器时出错或超时: {str(e)}"); return False

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout: self.log("ERROR", f"等待响应超时 ({timeout}秒)。"); return False

            try:
                 all_blocks = self.page.locator(response_block_selector)
                 count = await all_blocks.count()
                 if count == 0: await asyncio.sleep(2); continue

                 last_block = all_blocks.last
                 try: current_content = await last_block.inner_text(timeout=5000) # 缩短获取文本超时
                 except PlaywrightTimeoutError:
                      self.log("DEBUG", "获取最新AI响应内容超时..."); stable_count = 0; last_content_length = -1
                      await asyncio.sleep(1.0); continue # 缩短超时后等待

                 current_length = len(current_content)
                 stop_button = self.page.locator("button:has-text('Stop generating'), button:has-text('停止生成')").first
                 is_generating = False
                 try: is_generating = await stop_button.is_visible(timeout=500) # 快速检查
                 except PlaywrightTimeoutError: pass

                 if current_length > last_content_length: stable_count = 0
                 elif current_length == last_content_length and current_length > 0:
                      if is_generating: stable_count = 0
                      else: stable_count += 1; #self.log("DEBUG", f"内容稳定计数: {stable_count}/{STABLE_THRESHOLD}")
                 else: stable_count = 0

                 last_content_length = current_length

                 if stable_count >= STABLE_THRESHOLD:
                      self.log("SUCCESS", f"检测到AI响应已稳定 (最终长度: {current_length})。")
                      await asyncio.sleep(0.5); return True # 缩短稳定后等待

            except Exception as e:
                 self.log("WARNING", f"检查响应稳定状态时出错: {str(e)}"); stable_count = 0
            await asyncio.sleep(1.0) # 缩短检查间隔

    # ================== [ 核心修复 - 优化复制逻辑和超时 ] ==================
    async def copy_last_response_to_clipboard(self) -> bool:
        self.log("INFO", "正在执行终极复制策略...")
        start_copy_time = time.time()
        # 增加整体复制操作超时
        COPY_OVERALL_TIMEOUT = 25 # 秒

        response_block_selector = f"div.{AI_MESSAGE_CONTAINER_CLASS}"
        copy_button_selectors = [
            'button:has-text("复制")', 'button[aria-label*="Copy" i]',
            'button[class*="copy"]', 'span:has-text("复制")',
            'button > svg[class*="copy"]', "button:near(:text('重新生成'), 80)"
        ]

        while time.time() - start_copy_time < COPY_OVERALL_TIMEOUT:
            try:
                all_blocks = self.page.locator(response_block_selector)
                # 稍微等待确保消息块加载
                await all_blocks.first.wait_for(state='attached', timeout=5000)
                if await all_blocks.count() == 0:
                    self.log("WARNING", "未找到AI消息容器，稍后重试...")
                    await asyncio.sleep(1); continue # 等待1秒重试

                last_container = all_blocks.last

                # 策略一：容器内查找
                #self.log("DEBUG", "策略一：在最后一个AI消息容器内查找...")
                for selector in copy_button_selectors:
                    if time.time() - start_copy_time > COPY_OVERALL_TIMEOUT: break # 检查内部循环超时
                    try:
                        copy_button = last_container.locator(selector).first
                        # 使用 click 自带的等待，设置合理超时
                        await copy_button.scroll_into_view_if_needed(timeout=3000) # 快速滚动
                        await asyncio.sleep(0.2)
                        await copy_button.click(timeout=7000) # 7秒点击超时
                        self.log("SUCCESS", f"策略一成功：已点击消息容器内的复制按钮 (selector: {selector})。")
                        await asyncio.sleep(0.5); return True
                    except Exception: pass # 静默失败，尝试下一个选择器或策略

                # 策略二：全局查找 (如果策略一所有选择器都失败)
                #self.log("DEBUG", "策略二：全局搜索最后一个复制按钮...")
                for selector in copy_button_selectors:
                     if time.time() - start_copy_time > COPY_OVERALL_TIMEOUT: break
                     try:
                          all_found_buttons = self.page.locator(selector)
                          count = await all_found_buttons.count()
                          if count > 0:
                               last_button = all_found_buttons.last
                               await last_button.scroll_into_view_if_needed(timeout=3000)
                               await asyncio.sleep(0.2)
                               await last_button.click(timeout=7000)
                               self.log("SUCCESS", f"策略二成功：已全局点击最后一个复制按钮 (selector: {selector})。")
                               await asyncio.sleep(0.5); return True
                     except Exception: pass
            
            except Exception as e:
                 # 查找容器或其他意外错误
                 self.log("WARNING", f"查找或尝试复制时出错: {str(e)}，稍后重试...")
            
            # 如果没找到或没成功，等待一小段时间再重试
            await asyncio.sleep(1.5)

        # 如果循环结束仍未成功
        self.log("ERROR", f"所有复制策略在 {COPY_OVERALL_TIMEOUT} 秒内均失败。")
        return False
    # ====================================================================

    async def cleanup(self):
        try:
            if self.page and not self.page.is_closed(): await self.page.close()
            if self.context: await self.context.close()
            if self.browser and self.browser.is_connected(): await self.browser.close()
            if self.playwright: await self.playwright.stop()
            self.log("INFO", "浏览器资源已清理。")
        except Exception as e:
            self.log("ERROR", f"清理 BrowserController 出错: {str(e)}\n{traceback.format_exc()}")