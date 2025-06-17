import os
import platform
import shutil
import subprocess
import time
from typing import Optional

from .AdbController import AdbController


# --- 模块二：网络抓包 ---
class MitmproxyCapture:
    def __init__(self, controller: AdbController, output_dir: str):
        self.controller = controller
        self.output_dir = os.path.join(output_dir, "capture")
        os.makedirs(self.output_dir, exist_ok=True)
        self.proxy_port = 8080
        self.mitm_process = None
        self.flows_file = os.path.join(self.output_dir, "flows.json")
        if not shutil.which("mitmdump"):
            raise EnvironmentError("mitmproxy未安装或未在PATH中")

    def start(self) -> bool:
        script_path = self._create_mitm_script()
        default_conf_dir = os.path.join(os.path.expanduser("~"), ".mitmproxy")
        cmd = [
            "mitmdump",
            "-p",
            str(self.proxy_port),
            "-s",
            script_path,
            "--set",
            f"confdir={default_conf_dir}",
            "--ssl-insecure",
        ]
        print("正在启动mitmproxy...")
        creationflags = (
            subprocess.CREATE_NEW_CONSOLE
            if platform.system() == "Windows"
            else 0
        )
        self.mitm_process = subprocess.Popen(cmd, creationflags=creationflags)
        time.sleep(3)
        if self.mitm_process.poll() is None:
            print(f"  ✓ mitmproxy已启动 (代理: 127.0.0.1:{self.proxy_port})")
            return self._configure_android_proxy()
        else:
            print("  ✗ mitmproxy启动失败")
            return False

    def stop(self) -> Optional[str]:
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
        # 10.0.2.2是官方模拟器访问宿主机的IP, 其他模拟器可能是不同IP
        host_ip = "192.168.0.162"
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
