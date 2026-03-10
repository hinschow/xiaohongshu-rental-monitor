#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知发送模块
"""

import sys
import io

# 强制 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def format_notification(listing):
    """格式化通知消息"""
    tags_str = "、".join(listing.get('tags', []))
    
    message = f"""🏠 新房源提醒

📍 位置：{listing.get('location', '未知')}
💰 价格：{listing.get('price', '未知')}元/月
🏡 房型：{listing.get('room_type', '未知')}
📅 发布：{listing.get('published_at', '未知')}
"""
    
    if tags_str:
        message += f"\n✨ 亮点：{tags_str}\n"
    
    message += f"\n🔗 查看详情：{listing.get('link', '')}"
    
    return message


def send_notifications(listings, config):
    """发送通知"""
    if not config['notification']['enabled']:
        print("通知已禁用")
        return
    
    for listing in listings:
        message = format_notification(listing)
        print("\n" + "=" * 50)
        print("发送通知:")
        print(message)
        print("=" * 50)
        
        # TODO: 实际发送到 Telegram
        # 在 OpenClaw 环境中，可以直接 print 消息
        # OpenClaw 会自动发送到 Telegram
        
    print(f"\n✓ 已发送 {len(listings)} 条通知")
