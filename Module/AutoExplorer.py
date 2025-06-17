import time

import uiautomator2 as u2
from uiautomator2 import UiObjectNotFoundError

from .AdbController import AdbController


# --- 模块：智能UI探索器 (基于 uiautomator2) ---
class AutoExplorer:
    """
    使用 uiautomator2 智能探索 App UI.
    """

    def __init__(self, controller: AdbController):
        self.d = controller.device
        self.controller = controller
        self.visited_elements = set()
        self.last_action_time = time.time()
        self.idle_for_back_press = 15  # 如果15秒没有新操作，则按返回键

        self.INPUT_TEXTS = [
            "testuser",
            "123456",
            "test@example.com",
            "My Test Note",
        ]
        self.CONFIRM_KEYWORDS_REGEX = r"(?i)登录|确定|下一步|完成|同意|搜索|发布|login|ok|next|done|agree|confirm|search|submit"
        self.TAB_CLASS_REGEX = r"(?i).*tab.*"

        # NEW: Keywords for bottom navigation tabs
        self.BOTTOM_NAV_KEYWORDS = [
            "首页",
            "钱包",
            "客服",
            "我的",
            "发现",
            "消息",
            "通讯录",
            "社区",
            "Home",
            "About",
            "Profile",
            "Wallet",
            "Community",
            "Message",
        ]

    def explore_step(self):
        """执行一步探索操作，按优先级策略执行"""
        if self._handle_system_popups():
            time.sleep(1)
            return

        if self._handle_input_fields():
            time.sleep(2)
            return

        # NEW: Add specific handling for bottom navigation
        if self._handle_bottom_navigation():
            time.sleep(2)
            return

        if self._handle_tabs():  # Handles general tabs (not bottom nav)
            time.sleep(2)
            return

        if self._handle_general_clickables():
            time.sleep(2)
            return

        if time.time() - self.last_action_time > self.idle_for_back_press:
            print("  [探索] 未找到可操作的新元素，尝试按返回键...")
            self.d.press("back")
            self.last_action_time = time.time()
            self.visited_elements.clear()

    def _get_element_signature(self, element: u2.UiObject) -> str:
        """为元素创建一个唯一的、稳定的签名"""
        info = element.info
        # Use a combination of class, resourceId, and text/desc for a robust signature
        return f"{info.get('className')}-{info.get('resourceId')}-{info.get('text')}-{info.get('contentDescription')}"

    def _perform_action(
        self, element: u2.UiObject, action_type="click", text_to_input=None
    ):
        signature = self._get_element_signature(element)
        if signature in self.visited_elements:
            return False

        try:
            if not element.exists:
                return False
            if action_type == "click":
                element.click()
            elif action_type == "input" and text_to_input:
                element.set_text(text_to_input)

            self.visited_elements.add(signature)
            self.last_action_time = time.time()
            return True
        except UiObjectNotFoundError:
            return False

    def _handle_system_popups(self) -> bool:
        """处理常见的系统权限弹窗"""
        # More robust selector for different Android versions
        allow_button = self.d(
            resourceIdMatches=r".*permission_allow_button.*", clickable=True
        )
        if allow_button.exists:
            print("  [探索策略] 检测到系统权限弹窗，点击允许。")
            allow_button.click()
            return True
        return False

    def _handle_input_fields(self) -> bool:
        for el in self.d(className="android.widget.EditText"):
            if self._get_element_signature(el) not in self.visited_elements:
                print(
                    f"  [探索策略] 发现输入框: {el.info.get('resourceId') or el.info.get('text')}"
                )
                input_text = self.INPUT_TEXTS[
                    len(self.visited_elements) % len(self.INPUT_TEXTS)
                ]
                # Click before setting text to ensure focus
                el.click()
                time.sleep(0.5)
                self._perform_action(
                    el, action_type="input", text_to_input=input_text
                )
                time.sleep(1)

                confirm_button = self.d(
                    textMatches=self.CONFIRM_KEYWORDS_REGEX, clickable=True
                )
                if confirm_button.exists:
                    print(
                        f"  [探索策略] 找到并点击确认按钮: {confirm_button.info.get('text')}"
                    )
                    confirm_button.click()
                return True
        return False

    def _handle_bottom_navigation(self) -> bool:
        """
        NEW METHOD: Specifically finds and clicks unvisited main bottom navigation tabs.
        """
        _, screen_height = self.d.window_size()
        # Bottom navigation is typically in the bottom 15% of the screen
        bottom_area_start_y = screen_height * 0.85

        for keyword in self.BOTTOM_NAV_KEYWORDS:
            # Find clickable elements with the keyword text
            for el in self.d(text=keyword, clickable=True):
                bounds = el.info.get("bounds", {})
                # Heuristic: Ensure the element is in the bottom area of the screen
                if bounds.get("top", 0) < bottom_area_start_y:
                    continue

                signature = self._get_element_signature(el)
                if signature not in self.visited_elements:
                    print(f"  [探索策略] 发现并点击底部导航: '{keyword}'")
                    self._perform_action(el)
                    return True  # Action performed, end this exploration step
        return False

    def _handle_tabs(self) -> bool:
        """查找并点击未访问过的通用标签页 (e.g., top tabs)"""
        for el in self.d(classNameMatches=self.TAB_CLASS_REGEX, clickable=True):
            signature = self._get_element_signature(el)
            if signature not in self.visited_elements:
                print(
                    f"  [探索策略] 发现并点击通用标签页: {el.info.get('text') or el.info.get('contentDescription')}"
                )
                self._perform_action(el)
                return True
        return False

    def _handle_general_clickables(self) -> bool:
        """点击其他通用的、未访问过的可点击元素"""
        # CORRECTED LINE: Removed .all() from the end of the selector
        for el in self.d(clickable=True):
            if el.info.get("className") == "android.widget.EditText":
                continue
            if "com.android.systemui" in (el.info.get("packageName") or ""):
                continue

            # Heuristic: Avoid re-clicking bottom nav tabs if already handled
            if el.info.get("text") in self.BOTTOM_NAV_KEYWORDS:
                _, screen_height = self.d.window_size()
                if (
                    el.info.get("bounds", {}).get("top", 0)
                    > screen_height * 0.85
                ):
                    continue

            signature = self._get_element_signature(el)
            if signature not in self.visited_elements:
                print(
                    f"  [探索策略] 点击通用元素: {el.info.get('className')} - {el.info.get('text') or el.info.get('contentDescription')}"
                )
                self._perform_action(el)
                return True
        return False
