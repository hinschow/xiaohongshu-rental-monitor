#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试爬虫功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from datetime import datetime

from filter import extract_price, match_room_type, has_exclude_keywords, is_demand_post, is_stale_listing, filter_listings
from scraper import get_active_cooldown, is_verification_page


def test_extract_price():
    """测试价格提取"""
    assert extract_price("宝安两房 3200元/月") == 3200
    assert extract_price("3000-3500元") == 3000
    assert extract_price("租金3200") == 3200
    print("✓ 价格提取测试通过")


def test_match_room_type():
    """测试房型匹配"""
    assert match_room_type("2室1厅精装", "2室1厅") == True
    assert match_room_type("两房一厅", "2室1厅") == True
    assert match_room_type("1室1厅", "2室1厅") == False
    print("✓ 房型匹配测试通过")


def test_exclude_keywords():
    """测试排除关键词"""
    assert has_exclude_keywords("转租房源", ["转租", "短租"]) == True
    assert has_exclude_keywords("正常出租", ["转租", "短租"]) == False
    print("✓ 排除关键词测试通过")


def test_is_demand_post():
    """测试求租/找房需求帖识别"""
    assert is_demand_post("求租 宝安两房一厅，预算3500") == True
    assert is_demand_post("房东看过来，想租宝安中心两房") == True
    assert is_demand_post("宝安中心两房一厅房东直租，拎包入住") == False
    print("✓ 需求帖识别测试通过")


def test_filter_listings_keeps_unknown_price_but_rejects_demand_posts():
    config = {
        "filters": {"price_min": None, "price_max": None, "room_type": "2室1厅", "preferred_tags": []},
        "search": {"exclude_keywords": ["短租", "日租"]}
    }
    listings = [
        {
            "title": "宝安中心两房一厅房东直租",
            "description": "近地铁，未写价格",
            "detail_text": "",
            "tags": [],
            "room_type": "2室1厅"
        },
        {
            "title": "求租宝安中心两房一厅",
            "description": "预算3500",
            "detail_text": "",
            "tags": [],
            "room_type": None
        }
    ]
    filtered = filter_listings(listings, config)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "宝安中心两房一厅房东直租"
    assert filtered[0].get("price_unknown") == True
    print("✓ 保留未标价房源并过滤需求帖测试通过")


def test_is_stale_listing():
    assert is_stale_listing("【已转租】宝安中心两房一厅") == True
    assert is_stale_listing("已搬走，房子转出") == True
    assert is_stale_listing("宝安中心两房一厅房东直租") == False
    print("✓ 失效帖识别测试通过")


def test_get_active_cooldown():
    """测试冷却期判断"""
    state = {"cooldown_until": "2026-03-12 16:30:00"}
    assert get_active_cooldown(state, now=datetime(2026, 3, 12, 16, 0, 0)) is not None
    assert get_active_cooldown(state, now=datetime(2026, 3, 12, 16, 31, 0)) is None
    print("✓ 冷却期判断测试通过")


class FakeElement:
    def __init__(self, text="", visible=True):
        self._text = text
        self._visible = visible

    def is_visible(self):
        return self._visible

    def inner_text(self):
        return self._text


class FakePage:
    def __init__(self, text="", title="", url="https://www.xiaohongshu.com", selector_map=None):
        self._text = text
        self._title = title
        self.url = url
        self._selector_map = selector_map or {}

    def inner_text(self, selector):
        assert selector == "body"
        return self._text

    def title(self):
        return self._title

    def query_selector_all(self, selector):
        value = self._selector_map.get(selector, [])
        if isinstance(value, list):
            return value
        return [value] if value else []

    def query_selector(self, selector):
        value = self._selector_map.get(selector)
        if isinstance(value, list):
            return value[0] if value else None
        return value


def test_is_verification_page():
    """测试验证页识别"""
    blocked = FakePage(text="请完成安全验证后继续访问")
    normal = FakePage(
        text="发现 消息 通知 我 搜索 这里是正常的租房搜索结果页面",
        selector_map={
            'input[placeholder*="搜索"]': FakeElement(visible=True)
        }
    )
    ambiguous = FakePage(
        text="请先登录后查看更多内容",
        selector_map={
            'input[placeholder*="搜索"]': FakeElement(visible=True)
        }
    )
    assert is_verification_page(blocked) == True
    assert is_verification_page(normal) == False
    assert is_verification_page(ambiguous) == False
    print("✓ 验证页识别测试通过")


def test_notification_format():
    from notifier import format_notification
    listing = {
        "title": "宝安中心两房一厅房东直租",
        "description": "近地铁，精装修，拎包入住",
        "location": "宝安中心",
        "price": None,
        "room_type": "2室1厅",
        "published_at": "2026-03-12",
        "tags": ["近地铁", "精装修"],
        "link": "https://www.xiaohongshu.com/explore/test"
    }
    message = format_notification(listing)
    assert "📝 标题：宝安中心两房一厅房东直租" in message
    assert "📄 摘要：近地铁，精装修，拎包入住" in message
    assert "💰 价格：未标价" in message
    assert "🔗 链接：https://www.xiaohongshu.com/explore/test" in message
    print("✓ 通知格式测试通过")


if __name__ == "__main__":
    test_extract_price()
    test_match_room_type()
    test_exclude_keywords()
    test_is_demand_post()
    test_filter_listings_keeps_unknown_price_but_rejects_demand_posts()
    test_is_stale_listing()
    test_get_active_cooldown()
    test_is_verification_page()
    test_notification_format()
    print("\n所有测试通过！")
