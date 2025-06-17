import os
import threading
import time
from datetime import datetime
from typing import List

from .AdbController import AdbController


# --- 模块一：界面监控 ---
class UiChangeMonitor:
    def __init__(self, controller: AdbController, output_dir: str):
        self.controller = controller
        self.output_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(self.output_dir, exist_ok=True)
        self._monitoring = False
        self.last_ui_hash = None
        self.screenshot_paths: List[str] = []
        self.thread = None

    def start(self, interval: float = 2.0):
        self._monitoring = True
        self.thread = threading.Thread(
            target=self._monitor_loop, args=(interval,)
        )
        self.thread.start()
        print("  ✓ 界面变化监控已启动...")

    def stop(self):
        self._monitoring = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        print(
            f"  ✓ 界面变化监控已停止，共截取 {len(self.screenshot_paths)} 张图片。"
        )

    def _monitor_loop(self, interval: float):
        self._take_screenshot_if_needed("initial")
        while self._monitoring:
            current_ui_hash = self.controller.get_ui_dump_hash()
            if current_ui_hash and current_ui_hash != self.last_ui_hash:
                print(
                    f"  [监控] 检测到界面变化 (Hash: ...{current_ui_hash[-6:]})，正在截图..."
                )
                self._take_screenshot_if_needed(
                    f"change_{len(self.screenshot_paths)}"
                )
                self.last_ui_hash = current_ui_hash
            time.sleep(interval)

    def _take_screenshot_if_needed(self, name: str):
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)
        if self.controller.take_screenshot(filepath):
            self.screenshot_paths.append(filepath)
            print(f"    ✓ 截图已保存: {filepath}")
        else:
            print("    ✗ 截图失败")
