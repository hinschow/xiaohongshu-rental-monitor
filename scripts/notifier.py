#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知发送模块

说明：这里不直接调用 Telegram API。
在 OpenClaw 场景下，脚本只负责把整理好的通知内容打印出来，
再由上层会话/cron agent 读取输出并通过当前聊天通道转发给用户。
"""

import sys
import io

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


def send_notifications(listings, config):
    """发送通知到 Telegram"""
    if not config['notification']['enabled']:
        print("通知已禁用")
        return

    import os
    import json
    from urllib.request import urlopen, Request
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('RENTAL_CHAT_ID') or os.getenv('NEWS_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("⚠️ 缺少 TELEGRAM_BOT_TOKEN 或 RENTAL_CHAT_ID 环境变量，仅打印通知内容")
        for idx, listing in enumerate(listings, start=1):
            message = format_notification(listing)
            print("\n" + "=" * 50)
            print(f"通知候选 {idx}/{len(listings)}:")
            print(message)
            print("=" * 50)
        print(f"\n✓ 已生成 {len(listings)} 条通知内容（等待 OpenClaw 转发）")
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    sent_count = 0
    
    for idx, listing in enumerate(listings, start=1):
        message = format_notification(listing)
        print("\n" + "=" * 50)
        print(f"通知候选 {idx}/{len(listings)}:")
        print(message)
        print("=" * 50)
        
        try:
            payload = json.dumps({
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": False
            }).encode('utf-8')
            
            req = Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=10) as response:
                if response.status == 200:
                    sent_count += 1
                else:
                    print(f"⚠️ Telegram 发送失败: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️ Telegram 发送异常: {e}")
    
    print(f"\n✓ 已发送 {sent_count}/{len(listings)} 条通知到 Telegram")
