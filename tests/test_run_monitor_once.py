#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
import os

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from run_monitor_once import build_message


def test_build_message_ok():
    summary = {
        "status": "ok",
        "fetched": 12,
        "filtered": 4,
        "new_notifications": 2,
        "new_items": [
            {
                "title": "宝安中心两房一厅房东直租",
                "location": "宝安中心",
                "price": None,
                "room_type": "2室1厅",
                "published_at": "2026-03-12",
                "link": "https://example.com/1"
            }
        ]
    }
    msg = build_message(summary)
    assert "本轮监控完成" in msg
    assert "- 新房源：2 条" in msg
    assert "宝安中心两房一厅房东直租" in msg
    assert "https://example.com/1" in msg
    print("✓ 运行摘要格式测试通过")


if __name__ == "__main__":
    test_build_message_ok()
    print("所有测试通过！")
