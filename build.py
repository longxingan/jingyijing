#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静一静 v3 打包脚本
"""

import subprocess
import sys
import os


def build():
    """使用 PyInstaller 打包"""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "静一静_v3",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        # 隐藏控制台
        "--hide-console", "hide-early",
        # 添加数据文件
        "--add-data", "jingyijing_config.json;.",
        "--add-data", "quotes.txt;.",
        # 包含 ttkbootstrap 主题
        "--collect-data", "ttkbootstrap",
        # 包含 pystray
        "--collect-data", "pystray",
        # 图标
        "--icon", "icon.ico" if os.path.exists("icon.ico") else "NONE",
        "main.py"
    ]

    print("开始打包...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode == 0:
        print("\n打包成功！")
        print("输出文件: dist/静一静_v3.exe")
    else:
        print("\n打包失败！")
        sys.exit(1)


if __name__ == "__main__":
    build()
