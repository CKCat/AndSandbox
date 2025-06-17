# --- 主控制流程 ---
import json
import os
import time
from datetime import datetime
from typing import Optional

from .AdbController import AdbController
from .ApkAnalyzer import ApkAnalyzer
from .AutoExplorer import AutoExplorer
from .MitmproxyCapture import MitmproxyCapture
from .UiChangeMonitor import UiChangeMonitor


class APKTestSuite:
    def __init__(self, device_id: Optional[str] = None, output: str = ""):
        self.controller = AdbController(device_id)
        self.output_dir = f"{output}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"\n测试结果将保存到: {self.output_dir}\n")

        self.apk_analyzer = ApkAnalyzer()
        self.ui_monitor = UiChangeMonitor(self.controller, self.output_dir)
        self.network_capture = MitmproxyCapture(
            self.controller, self.output_dir
        )
        self.explorer = AutoExplorer(self.controller)

    def run(self, apk_path: str, test_duration: int = 60):
        final_report = {"test_start_time": datetime.now().isoformat()}
        package_name = None
        try:
            print("\n--- 步骤1: 静态分析 ---\n")
            analysis_result = self.apk_analyzer.get_analysis(apk_path)
            final_report["static_analysis"] = analysis_result
            if "error" in analysis_result:
                raise ValueError(analysis_result["error"])
            package_name = analysis_result["package_name"]

            print("\n--- 步骤2: 启动网络抓包 ---\n")
            if not self.network_capture.start():
                print("警告: 网络抓包启动失败，将继续进行测试...")

            print("\n--- 步骤3: 安装APK ---\n")
            # 卸载旧版本，确保干净环境
            self.controller.uninstall_app(package_name)
            if not self.controller.install_apk(apk_path):
                raise RuntimeError("APK安装失败，测试终止。")

            print("\n--- 步骤4: 启动应用、监控并进行智能探索 ---\n")
            if not self.controller.start_app(package_name):
                raise RuntimeError("应用启动失败，测试终止。")

            self.ui_monitor.start()

            print(f"\n应用运行中，将进行智能探索 {test_duration} 秒...")
            start_time = time.time()
            while time.time() - start_time < test_duration:
                remaining_time = int(test_duration - (time.time() - start_time))
                print(f"  测试倒计时: {remaining_time} 秒", end="\r")
                self.explorer.explore_step()
                time.sleep(1)  # 短暂间隔，避免CPU过载

            print("\n探索时间到。\n")

        except (ValueError, RuntimeError, KeyboardInterrupt) as e:
            print(f"\n测试过程中发生错误或被中断: {e}")
        finally:
            print("\n--- 步骤5: 清理与报告 ---\n")
            self.ui_monitor.stop()
            final_report["screenshots"] = self.ui_monitor.screenshot_paths
            flows_file = self.network_capture.stop()
            if flows_file:
                try:
                    with open(flows_file, "r", encoding="utf-8") as f:
                        final_report["network_flows"] = json.load(f)
                except (IOError, json.JSONDecodeError):
                    final_report["network_flows"] = "抓包结果为空或读取失败"
            if package_name:
                self.controller.uninstall_app(package_name)
            final_report["test_end_time"] = datetime.now().isoformat()
            report_path = os.path.join(self.output_dir, "final_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(final_report, f, indent=4, ensure_ascii=False)
            print(f"\n测试完成！详细报告已保存至: {report_path}")
            print("=" * 60)
