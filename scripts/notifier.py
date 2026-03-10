#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知发送模块
"""

import sys
import io

# 强制 UTF-8 编码
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def format_notification(listing):
    """格式化通知消息"""
    tags_str = "、".join(listing.get('tags', []))
    price_str = f"{listing.get('price', '未知')}元/月" if listing.get('price') else "未标价"

    message = f"""🏠 新房源提醒

📍 位置：{listing.get('location', '未知')}
💰 价格：{price_str}
🏡 房型：{listing.get('room_type') or '未标注'}
📅 发布：{listing.get('published_at') or '未知'}
"""

    if tags_str:
        message += f"\n✨ 亮点：{tags_str}\n"

    message += f"\n🔗 查看详情：{listing.get('link', '')}"

    return message


def send_notifications(listings, config):
    """发送通知 - 打印格式化消息，OpenClaw 会处理 Telegram 推送"""
    if not config['notification']['enabled']:
        print("通知已禁用")
        return

    for listing in listings:
        message = format_notification(listing)
        print("\n" + "=" * 50)
        print("发送通知:")
        print(message)
        print("=" * 50)

    print(f"\n✓ 已发送 {len(listings)} 条通知")
