import hashlib
import os
import re
import subprocess
import time
from typing import List, Optional, Tuple

import uiautomator2 as u2


# --- 工具类：ADB命令执行 ---
class AdbController:
    """
    设备控制器，使用uiautomator2封装了ADB和UI操作。
    """

    def __init__(self, device_id: Optional[str] = None):
        print("正在连接设备...")
        try:
            # The u2.connect() call itself handles waiting for the device.
            self.device = u2.connect(device_id)

            # self.device.wait_for_device(timeout=20)  # <-- THIS LINE IS REMOVED / CAUSES THE ERROR

            # We can directly check for the device info to confirm connection.
            device_info = self.device.device_info
            if not device_info.get("serial"):
                # Sometimes connect returns an object even on failure, this is a robust check
                raise u2.exceptions.ConnectError("Failed to get device serial.")

            print(
                f"  ✓ 设备连接成功: {device_info.get('model')} (Android {device_info.get('version')})"
            )
            self.device_id = self.device.serial
        except Exception as e:
            # The error message is updated to be more generic and helpful.
            raise EnvironmentError(
                f"连接设备失败: {e}\n请确保设备已通过ADB连接，并已成功运行 'python -m uiautomator2 init'"
            )

    def install_apk(self, apk_path: str) -> bool:
        if not os.path.exists(apk_path):
            print(f"错误: APK文件不存在 -> {apk_path}")
            return False

        print(f"正在安装APK: {os.path.basename(apk_path)}...")
        try:
            # Install the app without the 'grant_permissions' argument.
            # The AutoExplorer will handle permission popups as they appear.
            self.device.app_install(apk_path)
            print("  ✓ APK安装成功")
            return True

        except Exception as e:
            print(f"  ✗ APK安装失败: {e}")
            return False

    def uninstall_app(self, package_name: str) -> bool:
        print(f"正在卸载应用: {package_name}...")
        try:
            # We now wrap the check in a try block.
            # If app_info() succeeds, it means the app is installed.
            if self.device.app_info(package_name):
                print("  应用已安装，正在执行卸载...")
                self.device.app_uninstall(package_name)
                print("  ✓ 应用卸载成功")
        except u2.exceptions.AppNotFoundError:
            # If AppNotFoundError is raised, it's not an error for us.
            # It simply means the app isn't there, so there's nothing to do.
            print("  ✓ 应用未安装，无需卸载")
        except Exception as e:
            # Catch any other unexpected errors during the process.
            print(f"  ✗ 卸载过程中发生未知错误: {e}")
            return False

        return True

    def start_app(self, package_name: str) -> bool:
        print(f"正在启动应用: {package_name}...")
        try:
            # stop=True 确保每次都是全新启动
            self.device.app_start(package_name, stop=True)
            time.sleep(5)  # 等待应用加载
            print("  ✓ 应用启动成功")
            return True
        except Exception as e:
            print(f"  ✗ 应用启动失败: {e}")
            return False

    def take_screenshot(self, save_path: str) -> bool:
        try:
            # uiautomator2的截图方法直接保存到本地
            self.device.screenshot(save_path)
            return True
        except Exception as e:
            print(f"  ✗ 截图失败: {e}")
            return False

    def get_ui_dump_hash(self) -> Optional[str]:
        try:
            xml_content = self.device.dump_hierarchy()
            # 移除动态内容以获得稳定的哈希值
            xml_content = re.sub(r'text="\d{1,2}:\d{2}"', "", xml_content)
            xml_content = re.sub(r'content-desc=".*?"', "", xml_content)
            return hashlib.md5(xml_content.encode("utf-8")).hexdigest()
        except Exception:
            return None

    def _run_adb_command(
        self, command: List[str], timeout: int = 30
    ) -> Tuple[bool, str]:
        """保留一个基础的ADB命令执行器，用于代理设置等u2未直接封装的功能"""
        full_command = ["adb", "-s", self.device_id] + command
        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="ignore",
            )
            return (
                result.returncode == 0,
                result.stdout.strip() or result.stderr.strip(),
            )
        except Exception as e:
            return False, str(e)
