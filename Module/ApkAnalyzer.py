import hashlib
import os
from typing import Any, Dict

from apkutils import APK


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
