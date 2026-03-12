#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知发送模块
"""

import sys
import io
import os

try:
    import requests
except ImportError:
    requests = None

# 强制 UTF-8 编码
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def _truncate(text, limit=120):
    text = (text or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_notification(listing):
    """格式化通知消息"""
    tags_str = "、".join(listing.get('tags', []))
    price_str = f"{listing.get('price', '未知')}元/月" if listing.get('price') else "未标价"
    title = _truncate(listing.get('title') or '未提供标题', 80)
    description = _truncate(listing.get('description') or listing.get('detail_text') or '', 140)

    lines = [
        "🏠 新房源提醒",
        "",
        f"📝 标题：{title}",
    ]

    if description:
        lines.append(f"📄 摘要：{description}")

    lines.extend([
        f"📍 位置：{listing.get('location', '未知')}",
        f"💰 价格：{price_str}",
        f"🏡 房型：{listing.get('room_type') or '未标注'}",
        f"📅 发布：{listing.get('published_at') or '未知'}",
    ])

    if tags_str:
        lines.append(f"✨ 亮点：{tags_str}")

    lines.extend([
        "",
        f"🔗 链接：{listing.get('link', '')}"
    ])

    return "\n".join(lines)


def send_telegram_message(message, timeout=20):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token:
        raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN，无法发送 Telegram 通知")
    if not chat_id:
        raise RuntimeError("缺少 TELEGRAM_CHAT_ID，无法发送 Telegram 通知")
    if requests is None:
        raise RuntimeError("未安装 requests，无法发送 Telegram 通知")

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        api_url,
        json={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API 返回失败: {data}")
    return data


def send_notifications(listings, config):
    """发送通知：优先真实 Telegram 推送；失败时打印错误。"""
    if not config['notification']['enabled']:
        print("通知已禁用")
        return

    sent_count = 0
    for listing in listings:
        message = format_notification(listing)
        print("\n" + "=" * 50)
        print("准备发送通知:")
        print(message)
        print("=" * 50)

        try:
            send_telegram_message(message)
            sent_count += 1
            print("✓ Telegram 发送成功")
        except Exception as e:
            print(f"✗ Telegram 发送失败: {e}")

    print(f"\n✓ 成功发送 {sent_count}/{len(listings)} 条通知")
