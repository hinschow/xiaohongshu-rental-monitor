#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试爬虫功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from filter import extract_price, match_room_type, has_exclude_keywords


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


if __name__ == "__main__":
    test_extract_price()
    test_match_room_type()
    test_exclude_keywords()
    print("\n所有测试通过！")
