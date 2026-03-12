#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打开小红书持久化浏览器 profile，供人工扫码/过验证。

Usage:
    python scripts/open_profile.py
    python scripts/open_profile.py --url https://www.xiaohongshu.com/search_result?keyword=宝安转租
"""

import sys
import io
import time
import argparse
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
PROFILE_DIR = DATA_DIR / "playwright-profile"
PROFILE_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="打开小红书持久化浏览器，等待人工扫码")
    parser.add_argument("--url", default="https://www.xiaohongshu.com", help="打开的初始页面")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误: 请先安装 playwright")
        sys.exit(1)

    print("=" * 50)
    print("打开小红书持久化浏览器")
    print(f"Profile: {PROFILE_DIR}")
    print("请在弹出的浏览器中手动扫码/过验证")
    print("完成后直接关闭浏览器窗口，或在这里按 Ctrl+C")
    print("=" * 50)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=30000)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到退出信号，正在关闭浏览器...")
        finally:
            context.close()


if __name__ == "__main__":
    main()
