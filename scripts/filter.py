#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房源筛选逻辑
"""

import re


def extract_price(text):
    """从文本中提取价格，排除非租金数字"""
    exclude_prefix = r'(?:月入|年入|收入|工资|薪资|时薪|日薪|存款|存了|攒了|花了|花费|投入|首付|押金|中介费|服务费|面积|约)\s*'

    patterns = [
        r'(\d{4})\s*[-/~至到]\s*(\d{4})\s*(?:元|块|/月)',
        r'(\d{4})\s*(?:元|块)\s*/?\s*月',
        r'月租?\s*(\d{3,5})',
        r'(?:租金|价格|房租)[：:]\s*(\d{3,5})',
        r'(\d{4})\s*(?:元|块)',
        r'(\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            start = match.start()
            prefix_text = text[max(0, start - 10):start]
            if re.search(exclude_prefix + r'$', prefix_text):
                continue
            price = int(match.group(1))
            # 排除明显不是价格的数字（年份、面积等）
            if 500 <= price <= 20000:
                return price
    return None


def match_room_type(text, target_type):
    """匹配房型"""
    variants = [
        "2室1厅", "两室一厅", "2房1厅", "两房一厅",
        "2室", "两室", "2房", "两房"
    ]

    text_lower = text.lower()
    for variant in variants:
        if variant in text_lower:
            return True
    return False


def has_exclude_keywords(text, exclude_keywords):
    """检查是否包含排除关键词"""
    text_lower = text.lower()
    for keyword in exclude_keywords:
        if keyword in text_lower:
            return True
    return False


def calculate_score(listing, config):
    """计算房源评分"""
    score = 0

    # 优先标签加分
    preferred_tags = config['filters'].get('preferred_tags', [])
    for tag in listing.get('tags', []):
        if tag in preferred_tags:
            if tag == "近地铁":
                score += 10
            elif tag in ("精装", "精装修"):
                score += 5
            else:
                score += 3

    # 价格越接近中间值越好
    price = listing.get('price', 0)
    price_min = config['filters']['price_min']
    price_max = config['filters']['price_max']
    price_mid = (price_min + price_max) / 2

    if price:
        if price_min <= price <= price_max:
            price_diff = abs(price - price_mid)
            score += max(0, 10 - price_diff / 50)
        # 价格在范围内额外加分
        score += 5

    # 有详情文本加分（信息更完整）
    if listing.get('detail_text'):
        score += 3

    # 房型匹配加分
    if listing.get('room_type'):
        score += 5

    return round(score, 1)


def filter_listings(listings, config):
    """筛选房源

    策略：
    - 有价格：必须在范围内
    - 无价格：允许通过（标题提及租房相关即可），标记为 price_unknown
    - 排除关键词：始终生效
    - 房型：优先匹配，但不强制（很多帖子标题不写房型）
    """
    filtered = []
    filters = config['filters']
    exclude_keywords = config['search']['exclude_keywords']

    for listing in listings:
        title = listing.get('title', '')
        full_text = f"{title} {listing.get('description', '')} {listing.get('detail_text', '')}"

        # 排除关键词（始终生效）
        if has_exclude_keywords(full_text, exclude_keywords):
            continue

        # 价格筛选
        price = listing.get('price')
        if not price:
            price = extract_price(full_text)
            if price:
                listing['price'] = price

        if price:
            if price < filters['price_min'] or price > filters['price_max']:
                continue
        else:
            # 无价格：标记但允许通过
            listing['price_unknown'] = True

        # 计算评分（房型匹配会加分，但不作为硬性条件）
        if match_room_type(full_text, filters['room_type']):
            listing['room_match'] = True

        listing['score'] = calculate_score(listing, config)
        filtered.append(listing)

    # 按评分排序
    filtered.sort(key=lambda x: x.get('score', 0), reverse=True)

    return filtered
