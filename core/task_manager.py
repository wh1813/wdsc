"""
任务管理器 - 最终修复版 (移除模型选择调用)
"""
import asyncio
import re
from pathlib import Path
from typing import Optional, Callable, List, Dict

from PyQt5.QtWidgets import QApplication
from playwright.async_api import async_playwright

from core.cookie_manager import BrowserStorageManager
from core.browser_controller import BrowserController
from core.content_processor import ContentProcessor
from core.doc_generator import DocGenerator

class TaskManager:
    """任务管理器类"""

    def __init__(self, config: dict, cookie_manager: BrowserStorageManager, log_callback: Optional[Callable] = None):
        self.config = config
        self.cookie_manager = cookie_manager
        self.log_callback = log_callback
        self.browser_controller: Optional[BrowserController] = None
        self.content_processor = ContentProcessor(config=self.config, log_callback=self.log)
        self.doc_generator = DocGenerator(config=self.config, log_callback=self.log)
        self._initialized = False
        self._is_stopped = False
        self.playwright = None
        self.browser = None
        self.log("INFO", "任务管理器已创建")

    def stop(self):
        """设置停止标志位"""
        self._is_stopped = True

    def log(self, level: str, message: str):
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    async def initialize_from_session(self, port: int) -> bool:
        try:
            self.log("INFO", f"尝试连接到现有浏览器会话 (端口: {port})...")
            self.playwright = await async_playwright().start()
            browser_url = f"http://127.0.0.1:{port}"
            self.browser = await self.playwright.chromium.connect_over_cdp(browser_url)
            # 增加健壮性：检查contexts是否存在
            contexts = self.browser.contexts
            if not contexts:
                self.log("ERROR", "未找到浏览器上下文 (contexts)。")
                return False
            context = contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
            self.browser_controller = BrowserController(config=self.config, log_callback=self.log)
            self.browser_controller.playwright = self.playwright
            self.browser_controller.browser = self.browser
            self.browser_controller.context = context
            self.browser_controller.page = page
            self._initialized = True
            self.log("SUCCESS", f"成功连接到浏览器会话 (端口: {port})")
            return True
        except Exception as e:
            self.log("ERROR", f"连接浏览器会话失败: {str(e)}")
            return False

    async def initialize(self, account_name: Optional[str] = None) -> bool:
        try:
            self.log("INFO", f"初始化任务管理器 (账号: {account_name or '默认'})")
            cookies_data = self.cookie_manager.load_account(account_name) if account_name else None
            cookies = cookies_data.get("cookies") if cookies_data else None
            headless = not self.config.get("settings", {}).get("show_browser", False)
            self.browser_controller = BrowserController(config=self.config, log_callback=self.log)
            if not await self.browser_controller.initialize(cookies=cookies, headless=headless):
                 self.log("ERROR", "BrowserController 初始化失败。")
                 return False # 明确返回 False
            self._initialized = True
            self.log("SUCCESS", "任务管理器初始化完成 (Cookie 模式)")
            return True
        except Exception as e:
            self.log("ERROR", f"初始化失败: {str(e)}")
            return False

    async def process_single_title(self, title: str, model_name: str = None, output_dir: str = None) -> Dict:
        if not self._initialized: return {"success": False, "error": "任务管理器未初始化"}

        max_retries = 3
        for attempt in range(max_retries):
            if self._is_stopped:
                return {"success": False, "error": "任务被用户手动停止"}

            try:
                # 每次重试前也检查停止标志
                if self._is_stopped: return {"success": False, "error": "任务被用户手动停止"}

                if self.config.get("use_new_conversation", True):
                    await self.browser_controller.create_new_conversation()

                # ----------- [ 移除模型选择调用 ] -----------
                # if model_name and model_name != "自动选择":
                #     await self.browser_controller.select_model(model_name)
                # ------------------------------------------

                if not await self.browser_controller.send_message(message=title, system_prompt=self.config.get("system_prompt", "")):
                     # 发送失败通常比较严重，但允许重试
                     if attempt < max_retries - 1:
                          self.log("WARNING", f"发送消息失败 (尝试 {attempt + 1}/{max_retries})，刷新后重试...")
                          await self.browser_controller.refresh_page()
                          await asyncio.sleep(3) # 刷新后多等一会
                          continue # 进入下一次重试
                     else:
                          return {"success": False, "error": "发送消息连续失败"}

                if not await self.browser_controller.wait_for_response(timeout=self.config.get("settings", {}).get("timeout", 300)):
                    # 等待超时也允许重试
                    if attempt < max_retries - 1:
                          self.log("WARNING", f"等待响应超时 (尝试 {attempt + 1}/{max_retries})，刷新后重试...")
                          await self.browser_controller.refresh_page()
                          await asyncio.sleep(3)
                          continue
                    else:
                         return {"success": False, "error": "等待响应连续超时"}
                
                clipboard = QApplication.instance().clipboard()
                clipboard.clear()
                await asyncio.sleep(0.1)

                if not await self.browser_controller.copy_last_response_to_clipboard():
                     # 复制失败也允许重试
                     if attempt < max_retries - 1:
                          self.log("WARNING", f"复制内容失败 (尝试 {attempt + 1}/{max_retries})，刷新后重试...")
                          await self.browser_controller.refresh_page()
                          await asyncio.sleep(3)
                          continue
                     else:
                          return {"success": False, "error": "复制内容连续失败"}


                await asyncio.sleep(0.3) # 增加获取剪贴板内容前的等待
                content = clipboard.text()
                
                if content and not content.isspace():
                    processed_content = self.content_processor.process(content, title=title)
                    if not processed_content or len(processed_content) < 50:
                        # 内容处理失败通常不重试，直接标记失败
                        return {"success": False, "error": "响应内容处理后为空或太短", "raw_content": content}
                    
                    output_dir_path = Path(output_dir or self.config.get("output_dir", "./output")).resolve()
                    safe_title = re.sub(r'[\\/:*?"<>|\r\n]', "_", title).strip()[:100]
                    doc_path = output_dir_path / f"{safe_title}.docx"

                    if not self.doc_generator.create_document(title=title, content=processed_content, output_path=str(doc_path)):
                        # 保存失败也不重试
                        return {"success": False, "error": "保存文档失败"}

                    # 只有成功走到这里，才返回 True
                    return { "success": True, "title": title, "doc_path": str(doc_path) }

                # 如果 content 为空，进入重试逻辑
                self.log("WARNING", f"标题 '{title}' 第 {attempt + 1}/{max_retries} 次获取内容为空。")
                if attempt < max_retries - 1:
                    await self.browser_controller.refresh_page()
                    await asyncio.sleep(3) # 刷新后多等一会儿
                
            except Exception as e:
                 # 捕获到意外异常，通常不重试，记录错误并返回
                 self.log("ERROR", f"处理标题 '{title}' 时发生意外错误: {str(e)}\n{traceback.format_exc()}")
                 return {"success": False, "error": f"意外错误: {str(e)}"}

        # 如果循环结束仍未成功获取非空内容
        return {"success": False, "error": f"连续{max_retries}次获取内容为空或处理失败"}

    async def process_batch(
        self, titles: List[str], model_name: str = None, output_dir: str = None, progress_callback: Optional[Callable] = None,
    ) -> Dict:
        results = {"success": 0, "failed": 0, "details": []}
        success_counter_for_refresh = 0
        consecutive_failure_counter = 0

        for idx, title in enumerate(titles, 1):
            if self._is_stopped:
                self.log("WARNING", "任务已被用户中断，将退出批量处理。")
                results['error'] = "用户手动中止"
                break

            result = await self.process_single_title(title, model_name=model_name, output_dir=output_dir)
            
            if result.get("success"):
                results["success"] += 1
                success_counter_for_refresh += 1
                consecutive_failure_counter = 0
            else:
                results["failed"] += 1
                consecutive_failure_counter += 1
                # 检查 result['error'] 是否包含停止信息
                error_msg = result.get("error", "")
                if "停止" in error_msg or "中止" in error_msg:
                    results['error'] = error_msg # 记录具体的停止原因
                    break # 如果单次处理是因为停止而失败，则中止整个批处理

            if progress_callback: progress_callback(idx, len(titles), result)

            # 检查熔断
            if consecutive_failure_counter >= 3:
                self.log("ERROR", "已连续 3 个标题生成失败，任务自动中止！")
                results['error'] = "连续3次失败，任务中止"
                break

            # 检查刷新策略 (仅在成功后执行)
            if (idx < len(titles)) and result.get("success"):
                refresh_after_each = self.config.get("settings", {}).get("refresh_after_each", False)
                if refresh_after_each or (success_counter_for_refresh > 0 and success_counter_for_refresh % 5 == 0):
                    self.log("INFO", f"触发刷新条件 (每 {'1' if refresh_after_each else '5'} 次成功)，执行刷新...")
                    refresh_success = await self.browser_controller.refresh_page()
                    if refresh_success:
                         await asyncio.sleep(5) # 刷新成功后等待
                         # ----------- [ 移除模型选择调用 ] -----------
                         # if model_name and model_name != "自动选择":
                         #     await self.browser_controller.select_model(model_name)
                         # ------------------------------------------
                    else:
                         self.log("ERROR", "页面刷新失败，任务可能无法继续，将中止。")
                         results['error'] = "页面刷新失败，任务中止"
                         break # 刷新失败是严重问题，中止任务

            # 任务间常规间隔 (无论成功失败都等待)
            await asyncio.sleep(self.config.get("settings", {}).get("interval", 3))

        self.log("INFO", f"批量处理循环结束。成功: {results['success']}，失败: {results['failed']}")
        return results

    async def cleanup(self):
        try:
            if self.browser_controller: await self.browser_controller.cleanup()
            if self.playwright: await self.playwright.stop()
        except Exception as e:
            self.log("ERROR", f"清理时出错: {str(e)}")