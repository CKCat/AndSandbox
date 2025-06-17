#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android模拟器自动化测试脚本 - Windows版本
功能包括：APK安装运行、界面监控截图、mitmproxy网络抓包、APK解析等。
依赖：pip install apkutils opencv-python numpy pillow mitmproxy requests
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 确认依赖库是否安装
try:
    import cv2
    import numpy as np
    import requests
    from apkutils import APK
    from PIL import Image
except ImportError as e:
    print(f"缺少必要的库: {e}")
    print(
        "请执行: pip install apkutils opencv-python numpy pillow mitmproxy requests"
    )
    exit(1)


# --- 工具类：ADB命令执行 ---
class AdbController:
    """ADB命令执行器，封装了基础的ADB操作"""

    def __init__(self, device_id: Optional[str] = None):
        self.adb_path = self._find_adb()
        if not self.adb_path:
            raise EnvironmentError(
                "未找到ADB，请确保Android SDK已安装并配置好环境变量。"
            )

        self.device_id = device_id or self._get_first_device()
        if not self.device_id:
            raise EnvironmentError("未检测到任何连接的Android设备或模拟器。")

        print(f"ADB路径: {self.adb_path}")
        print(f"目标设备: {self.device_id}")

    def _find_adb(self) -> Optional[str]:
        adb_exe = "adb.exe" if platform.system() == "Windows" else "adb"
        adb_path = shutil.which(adb_exe)
        if adb_path:
            return adb_path

        # 针对Windows的常见路径
        if platform.system() == "Windows":
            common_paths = [
                os.path.join(
                    os.environ.get("LOCALAPPDATA", ""),
                    "Android",
                    "sdk",
                    "platform-tools",
                    adb_exe,
                ),
                os.path.join(
                    os.environ.get("ProgramFiles", ""),
                    "Android",
                    "Android Studio",
                    "jbr",
                    "bin",
                    adb_exe,
                ),
            ]
            for path in common_paths:
                if os.path.exists(path):
                    return path
        return None

    def _get_first_device(self) -> Optional[str]:
        success, output = self._run_adb_command(["devices"])
        if success:
            lines = output.strip().split("\n")[1:]
            for line in lines:
                if "\tdevice" in line:
                    return line.split("\t")[0]
        return None

    def _run_adb_command(
        self, command: List[str], timeout: int = 30
    ) -> Tuple[bool, str]:
        base_command = [self.adb_path, "-s", self.device_id]
        full_command = base_command + command
        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="ignore",
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stdout.strip() + result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, f"执行ADB命令失败: {e}"

    def install_apk(self, apk_path: str) -> bool:
        if not os.path.exists(apk_path):
            print(f"错误: APK文件不存在 -> {apk_path}")
            return False
        print(f"正在安装APK: {os.path.basename(apk_path)}...")
        success, output = self._run_adb_command(
            ["install", "-r", "-g", apk_path], timeout=180
        )
        if success and "Success" in output:
            print("  ✓ APK安装成功")
            return True
        else:
            print(f"  ✗ APK安装失败: {output}")
            return False

    def uninstall_app(self, package_name: str) -> bool:
        print(f"正在卸载应用: {package_name}...")
        success, output = self._run_adb_command(["uninstall", package_name])
        if success and "Success" in output:
            print("  ✓ 应用卸载成功")
            return True
        else:
            # 有时即使成功也没有Success字样，检查是否还存在
            is_installed, _ = self.is_app_installed(package_name)
            if not is_installed:
                print("  ✓ 应用卸载成功 (通过检查确认)")
                return True
            print(f"  ✗ 应用卸载失败: {output}")
            return False

    def start_app(self, package_name: str) -> bool:
        print(f"正在启动应用: {package_name}...")
        # 使用 monkey 启动，兼容性好
        cmd = [
            "shell",
            "monkey",
            "-p",
            package_name,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]
        success, output = self._run_adb_command(cmd)

        if success:
            print("  ✓ 应用启动命令已发送")
            time.sleep(5)  # 等待应用启动
            return True
        else:
            print(f"  ✗ 应用启动失败: {output}")
            return False

    def take_screenshot(self, save_path: str) -> bool:
        remote_path = "/sdcard/screenshot.png"
        success, _ = self._run_adb_command(["shell", "screencap", remote_path])
        if success:
            success, _ = self._run_adb_command(["pull", remote_path, save_path])
            self._run_adb_command(["shell", "rm", remote_path])  # 清理
            return success
        return False

    def get_ui_dump_hash(self) -> Optional[str]:
        """获取UI布局XML的哈希值，用于判断界面变化"""
        remote_path = "/sdcard/window_dump.xml"
        # 덤프 UI
        self._run_adb_command(["shell", "uiautomator", "dump", remote_path])
        # 获取文件内容
        success, xml_content = self._run_adb_command(
            ["shell", "cat", remote_path]
        )
        # 清理远程文件
        self._run_adb_command(["shell", "rm", remote_path])

        if success and xml_content:
            # 移除时间等易变节点，提高准确性
            xml_content = re.sub(r'text="\d{1,2}:\d{2}"', "", xml_content)
            xml_content = re.sub(r'content-desc=".*?"', "", xml_content)
            return hashlib.md5(xml_content.encode("utf-8")).hexdigest()
        return None

    def is_app_installed(self, package_name: str) -> Tuple[bool, str]:
        success, output = self._run_adb_command(
            ["shell", "pm", "list", "packages"]
        )
        if success:
            return package_name in output, output
        return False, output


# --- 模块一：界面监控 ---
class UiChangeMonitor:
    """使用adb dump uiautomator监控界面变化并截图"""

    def __init__(self, controller: AdbController, output_dir: str):
        self.controller = controller
        self.output_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(self.output_dir, exist_ok=True)

        self._monitoring = False
        self.last_ui_hash = None
        self.thread = None
        self.screenshot_paths: List[str] = []

    def start(self, interval: float = 2.0):
        """在后台线程中开始监控"""
        self._monitoring = True
        self.thread = threading.Thread(
            target=self._monitor_loop, args=(interval,)
        )
        self.thread.start()
        print("  ✓ 界面变化监控已启动...")

    def stop(self):
        """停止监控"""
        self._monitoring = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        print(
            f"  ✓ 界面变化监控已停止，共截取 {len(self.screenshot_paths)} 张图片。"
        )

    def _monitor_loop(self, interval: float):
        # 初始截图
        self._take_screenshot_if_needed("initial")

        while self._monitoring:
            current_ui_hash = self.controller.get_ui_dump_hash()

            # 如果UI发生变化，则截图
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


# --- 模块二：网络抓包 ---
class MitmproxyCapture:
    """使用mitmproxy进行网络抓包"""

    def __init__(self, controller: AdbController, output_dir: str):
        self.controller = controller
        self.output_dir = os.path.join(output_dir, "capture")
        os.makedirs(self.output_dir, exist_ok=True)

        self.proxy_port = 8080
        self.mitm_process = None
        self.flows_file = os.path.join(self.output_dir, "flows.json")

        if not shutil.which("mitmdump"):
            raise EnvironmentError(
                "mitmproxy未安装或未在PATH中，请执行: pip install mitmproxy"
            )

    def start(self) -> bool:
        """启动mitmproxy抓包"""
        script_path = self._create_mitm_script()

        # 获取默认的mitmproxy配置目录
        default_conf_dir = os.path.join(os.path.expanduser("~"), ".mitmproxy")

        # 确保默认配置目录存在，如果不存在，mitmproxy会自动创建
        # os.makedirs(default_conf_dir, exist_ok=True) # 这行通常不是必须的

        cmd = [
            "mitmdump",
            "-p",
            str(self.proxy_port),
            "-s",
            script_path,
            # 【关键修改】强制使用默认的、你已经安装过证书的配置目录
            "--set",
            f"confdir={default_conf_dir}",
            "--ssl-insecure",
        ]

        print("正在启动mitmproxy...")
        print(f"  命令: {' '.join(cmd)}")  # 打印命令方便调试

        print("正在启动mitmproxy...")
        # 在新窗口中启动，避免日志干扰主程序
        creationflags = (
            subprocess.CREATE_NEW_CONSOLE
            if platform.system() == "Windows"
            else 0
        )
        self.mitm_process = subprocess.Popen(cmd, creationflags=creationflags)
        print(self.mitm_process)
        time.sleep(3)  # 等待mitmproxy启动
        if self.mitm_process.poll() is None:
            print(f"  ✓ mitmproxy已启动 (代理: 127.0.0.1:{self.proxy_port})")
            return self._configure_android_proxy()
        else:
            print("  ✗ mitmproxy启动失败")
            return False

    def stop(self) -> Optional[str]:
        """停止抓包并清理代理"""
        print("正在停止mitmproxy...")
        self._clear_android_proxy()
        if self.mitm_process:
            self.mitm_process.terminate()
            try:
                self.mitm_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.mitm_process.kill()
            print("  ✓ mitmproxy已停止")

        return self.flows_file if os.path.exists(self.flows_file) else None

    def _create_mitm_script(self) -> str:
        # 将路径中的反斜杠替换为双反斜杠，以适应Python字符串
        safe_output_path = self.flows_file.replace("\\", "\\\\")
        script_content = f"""
import base64
import json

from mitmproxy import http

flows = []

def request(flow: http.HTTPFlow) -> None:
    if flow.request.host.find("ldmnq.com") != -1:
        return
    request_data = {{"method": flow.request.method,
        "url": flow.request.pretty_url,
        "host": flow.request.host,
        "headers": dict(flow.request.headers),
    }}
    # 初始化流量记录，response_data 置为空
    flow_entry = {{"request": request_data, "response": None}}
    flows.append(flow_entry)
    
    # 保存到文件
    with open(r'{safe_output_path}', 'w', encoding='utf-8') as f:
        json.dump(flows, f, indent=2, ensure_ascii=False)

def response(flow: http.HTTPFlow) -> None:
    if flow.request.host.find("ldmnq.com") != -1:
        return
    # 查找对应的请求
    for flow_entry in flows:
        if flow_entry["request"]["url"] == flow.request.pretty_url and flow_entry["response"] is None:
            content = ""
            if flow.response:
                try:
                    content = flow.response.text or base64.b64decode(flow.response.content).decode("utf-8", errors="ignore")
                except Exception:
                    content = "[Decode Error]"
                flow_entry["response"] = {{"status_code": flow.response.status_code,
                    "headers": dict(flow.response.headers),
                    "content": content,
                }}
            else:
                flow_entry["response"] = {{"status": "No response received"}}
            
            # 保存更新后的数据
            with open(r'{safe_output_path}', 'w', encoding='utf-8') as f:
                json.dump(flows, f, indent=2, ensure_ascii=False)
            break
    
"""
        script_path = os.path.join(self.output_dir, "mitm_script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        return script_path

    def _configure_android_proxy(self) -> bool:
        host_ip = "192.168.0.162"  # 模拟器访问宿主机的固定IP
        proxy_setting = f"{host_ip}:{self.proxy_port}"
        print(f"正在配置模拟器代理: {proxy_setting}...")
        success, _ = self.controller._run_adb_command(
            ["shell", "settings", "put", "global", "http_proxy", proxy_setting]
        )
        if success:
            print("  ✓ 代理配置成功")
            return True
        print("  ✗ 代理配置失败")
        return False

    def _clear_android_proxy(self) -> bool:
        print("正在清除模拟器代理...")
        success, _ = self.controller._run_adb_command(
            ["shell", "settings", "put", "global", "http_proxy", ":0"]
        )
        if success:
            print("  ✓ 代理已清除")
            return True
        print("  ✗ 代理清除失败")
        return False


# --- 模块三：APK静态分析 ---
class ApkAnalyzer:
    """使用apkutils进行APK静态分析"""

    def get_analysis(self, apk_path: str) -> Dict[str, Any]:
        print(f"正在静态分析APK: {os.path.basename(apk_path)}...")
        if not os.path.exists(apk_path):
            return {"error": "APK文件不存在"}

        try:
            apk = APK.from_file(apk_path)

            analysis = {
                "file_md5": hashlib.md5(
                    open(apk_path, "rb").read()
                ).hexdigest(),
                "package_name": apk.get_package_name(),
                "main_activity": apk.get_main_activities(),
            }
            print(f"  ✓ 分析完成，包名: {analysis['package_name']}")
            return analysis
        except Exception as e:
            return {"error": f"APK分析失败: {e}"}


# --- 主控制流程 ---
class APKTestSuite:
    """APK自动化测试套件"""

    def __init__(self, device_id: Optional[str] = None, output: str = ""):
        self.controller = AdbController(device_id)

        # 创建本次测试的主输出目录
        self.output_dir = f"{output}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"\n测试结果将保存到: {self.output_dir}\n")

        self.apk_analyzer = ApkAnalyzer()
        self.ui_monitor = UiChangeMonitor(self.controller, self.output_dir)
        self.network_capture = MitmproxyCapture(
            self.controller, self.output_dir
        )

    def run(self, apk_path: str, test_duration: int = 60):
        """执行完整的自动化测试流程"""

        final_report = {"test_start_time": datetime.now().isoformat()}
        package_name = None

        try:
            # 1. 静态分析
            print("\n--- 步骤1: 静态分析 ---\n")
            analysis_result = self.apk_analyzer.get_analysis(apk_path)
            final_report["static_analysis"] = analysis_result
            if "error" in analysis_result:
                raise ValueError(analysis_result["error"])
            package_name = analysis_result["package_name"]

            # 2. 启动网络抓包
            print("\n--- 步骤2: 启动网络抓包 ---\n")
            if not self.network_capture.start():
                print("警告: 网络抓包启动失败，将继续进行测试...")

            # 3. 安装APK
            print("\n--- 步骤3: 安装APK ---\n")
            if not self.controller.install_apk(apk_path):
                raise RuntimeError("APK安装失败，测试终止。")

            # 4. 启动应用并开始监控
            print("\n--- 步骤4: 启动应用并监控 ---\n")
            if not self.controller.start_app(package_name):
                raise RuntimeError("应用启动失败，测试终止。")

            self.ui_monitor.start()  # 后台启动监控

            print(f"\n应用运行中，将持续监控 {test_duration} 秒...")
            for i in range(test_duration):
                print(f"  测试倒计时: {test_duration - i} 秒", end="\r")
                time.sleep(1)
            print("\n测试时间到。\n")

        except (ValueError, RuntimeError, KeyboardInterrupt) as e:
            print(f"\n测试过程中发生错误或被中断: {e}")

        finally:
            print("\n--- 步骤5: 清理与报告 ---\n")
            # 停止监控
            self.ui_monitor.stop()
            final_report["screenshots"] = self.ui_monitor.screenshot_paths

            # 停止抓包
            flows_file = self.network_capture.stop()
            if flows_file:
                with open(flows_file, "r", encoding="utf8") as f:
                    final_report["network_flows"] = json.load(f)

            # 卸载应用
            if package_name:
                self.controller.uninstall_app(package_name)

            final_report["test_end_time"] = datetime.now().isoformat()

            # 保存最终报告
            report_path = os.path.join(self.output_dir, "final_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(final_report, f, indent=4, ensure_ascii=False)

            print(f"\n测试完成！详细报告已保存至: {report_path}")
            print("=" * 60)


if __name__ == "__main__":
    # --- 配置和运行 ---

    # 1. 请将你要测试的APK文件路径放在这里
    # 例如: "C:\\Users\\YourUser\\Downloads\\some_app.apk"
    # 注意Windows路径中的反斜杠需要写成双反斜杠 `\\` 或者使用正斜杠 `/`

    APK_FILE_PATH = "./9014e7c1ca7059c03dc5ee9072b83059.apk"

    # 2. 设置应用运行和监控的时长（秒）
    TEST_DURATION_SECONDS = 30

    # device = "emulator-5554"
    # output = os.path.basename(APK_FILE_PATH).replace(".apk", "")
    # suite = APKTestSuite(device_id=device, output=output)
    # suite.run(APK_FILE_PATH, TEST_DURATION_SECONDS)

    # 可选：指定特定设备ID，如果为None则自动选择第一个设备
    # device = "emulator-5554"
    for dirpath, dirnames, filenames in os.walk("apks"):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            print(full_path)
            device = "emulator-5554"
            output = os.path.basename(filename).replace(".apk", "")
            try:
                suite = APKTestSuite(device_id=device, output=output)
                suite.run(full_path, TEST_DURATION_SECONDS)
            except Exception as e:
                print(f"\n启动测试失败，环境配置错误: {e}")
                continue
