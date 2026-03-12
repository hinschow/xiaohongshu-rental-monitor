#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行一轮监控，并输出适合 OpenClaw 直接转发给用户的简短总结。

默认调用 scraper.py 的稳定模式（非无头）。
如需实验无头，可加 --headless。
"""

import json
import subprocess
import sys
import io
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
SUMMARY_FILE = DATA_DIR / "latest_run_summary.json"
SCRAPER = ROOT_DIR / "scripts" / "scraper.py"


def load_summary():
    if not SUMMARY_FILE.exists():
        return None
    return json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))


def format_price(item):
    return f"{item['price']}元/月" if item.get("price") else "未标价"


def format_item(item, idx):
    title = item.get("title") or "未提供标题"
    location = item.get("location") or "未知"
    room_type = item.get("room_type") or "未标注"
    published = item.get("published_at") or "未知"
    return (
        f"{idx}. {title}\n"
        f"   📍 {location}｜💰 {format_price(item)}｜🏡 {room_type}｜📅 {published}\n"
        f"   🔗 {item.get('link') or ''}"
    )


def build_message(summary):
    status = summary.get("status")
    if status == "cooldown":
        return (
            f"⚠️ 当前处于冷却期，暂未执行抓取。\n"
            f"原因：{summary.get('reason') or 'unknown'}\n"
            f"冷却至：{summary.get('cooldown') or 'unknown'}"
        )
    if status == "verification_blocked":
        return (
            f"⚠️ 这轮被小红书验证拦住了，需要你重新扫码/过验证。\n"
            f"原因：{summary.get('reason') or 'verification_blocked'}"
        )
    if status == "empty":
        return "这轮没抓到结果，可能是登录态或风控问题，我建议你让我再做一次可视化检查。"
    if status == "error":
        return f"❌ 监控运行报错：{summary.get('reason') or 'unknown error'}"

    lines = [
        "本轮监控完成。",
        f"- 抓取：{summary.get('fetched', 0)} 条",
        f"- 筛选后：{summary.get('filtered', 0)} 条",
        f"- 新房源：{summary.get('new_notifications', 0)} 条",
    ]

    items = summary.get("new_items") or []
    if items:
        lines.append("")
        lines.append("新房源：")
        for idx, item in enumerate(items, start=1):
            lines.append(format_item(item, idx))
    else:
        lines.append("")
        lines.append("这轮没有新的可通知房源。")

    return "\n".join(lines)


def main():
    extra_args = sys.argv[1:]
    cmd = [sys.executable, str(SCRAPER), *extra_args]
    proc = subprocess.run(cmd, cwd=str(ROOT_DIR), text=True)

    summary = load_summary()
    if not summary:
        print("❌ 未找到 latest_run_summary.json，无法生成摘要")
        sys.exit(proc.returncode or 1)

    print("\n" + "#" * 50)
    print("OPENCLAW_SUMMARY")
    print(build_message(summary))
    print("#" * 50)

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
