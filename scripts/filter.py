#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房源筛选逻辑
"""

import re


def extract_price(text):
    """从文本中提取价格"""
    # 匹配 3000-3500 或 3000元 等格式
    patterns = [
        r'(\d{4})\s*[-/~]\s*(\d{4})',  # 3000-3500
        r'(\d{4})\s*元',                # 3000元
        r'(\d{4})',                     # 3000
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def match_room_type(text, target_type):
    """匹配房型"""
    # 2室1厅的各种写法
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
            elif tag == "精装":
                score += 5
            else:
                score += 3
    
    # 价格越接近中间值越好
    price = listing.get('price', 0)
    price_min = config['filters']['price_min']
    price_max = config['filters']['price_max']
    price_mid = (price_min + price_max) / 2
    
    if price:
        price_diff = abs(price - price_mid)
        score += max(0, 10 - price_diff / 50)
    
    return score


def filter_listings(listings, config):
    """筛选房源"""
    filtered = []
    filters = config['filters']
    exclude_keywords = config['search']['exclude_keywords']
    
    for listing in listings:
        # 价格筛选
        price = listing.get('price')
        if not price:
            price = extract_price(listing.get('title', ''))
        
        if not price:
            continue
            
        if price < filters['price_min'] or price > filters['price_max']:
            continue
        
        # 房型筛选
        title = listing.get('title', '')
        if not match_room_type(title, filters['room_type']):
            continue
        
        # 排除关键词
        if has_exclude_keywords(title, exclude_keywords):
            continue
        
        # 计算评分
        listing['score'] = calculate_score(listing, config)
        filtered.append(listing)
    
    # 按评分排序
    filtered.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return filtered
