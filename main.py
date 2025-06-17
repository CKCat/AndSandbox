#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android模拟器自动化测试脚本 - Windows版本
功能包括：APK安装运行、界面监控截图、mitmproxy网络抓包、APK解析等。
依赖：pip install apkutils opencv-python numpy pillow mitmproxy requests
"""

import os

from Module.APKTestSuite import APKTestSuite

if __name__ == "__main__":
    # --- 配置和运行 ---

    # 1. 请将你要测试的APK文件路径放在这里
    # 例如: "C:\\Users\\YourUser\\Downloads\\some_app.apk"
    # 注意Windows路径中的反斜杠需要写成双反斜杠 `\\` 或者使用正斜杠 `/`

    APK_FILE_PATH = (
        r"D:\Code\pythonProjects\sandbox\9014e7c1ca7059c03dc5ee9072b83059.apk"
    )

    # 2. 设置应用运行和监控的时长（秒）
    TEST_DURATION_SECONDS = 30

    # device = "emulator-5554"
    # output = os.path.basename(APK_FILE_PATH).replace(".apk", "")
    # suite = APKTestSuite(device_id=device, output=output)
    # suite.run(APK_FILE_PATH, TEST_DURATION_SECONDS)

    # 可选：指定特定设备ID，如果为None则自动选择第一个设备
    device = "emulator-5554"
    for dirpath, dirnames, filenames in os.walk(
        r"D:\Code\pythonProjects\sandbox\apks"
    ):
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
