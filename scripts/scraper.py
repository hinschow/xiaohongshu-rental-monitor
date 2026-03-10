#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书租房信息爬虫
"""

import sys
import io
import json
import time
import random
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 强制 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 加载环境变量
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config" / "defaults.json"
DATA_DIR = ROOT_DIR / "data"
LISTINGS_FILE = DATA_DIR / "listings.json"
NOTIFIED_FILE = DATA_DIR / "notified.json"

# 确保数据目录存在
DATA_DIR.mkdir(exist_ok=True)


def load_config():
    """加载配置文件"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_listings():
    """加载已保存的房源数据"""
    if LISTINGS_FILE.exists():
        with open(LISTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_listings(listings):
    """保存房源数据"""
    with open(LISTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)


def load_notified():
    """加载已通知的房源ID"""
    if NOTIFIED_FILE.exists():
        with open(NOTIFIED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_notified(notified_ids):
    """保存已通知的房源ID"""
    with open(NOTIFIED_FILE, 'w', encoding='utf-8') as f:
        json.dump(notified_ids, f, ensure_ascii=False, indent=2)


def scrape_xiaohongshu(config):
    """
    爬取小红书租房信息
    
    TODO: 实现爬虫逻辑
    - 使用 playwright 模拟浏览器
    - 搜索关键词
    - 提取房源信息
    - 返回房源列表
    
    返回格式：
    [
        {
            "id": "unique_id",
            "title": "标题",
            "price": 3200,
            "location": "宝安中心区",
            "room_type": "2室1厅",
            "tags": ["近地铁", "精装"],
            "link": "https://...",
            "published_at": "2026-03-10 14:00:00",
            "scraped_at": "2026-03-10 14:50:00"
        }
    ]
    """
    print("开始爬取小红书...")
    
    # TODO: 实现实际爬虫逻辑
    # 这里返回示例数据用于测试
    return [
        {
            "id": f"test_{int(time.time())}",
            "title": "宝安中心区精装两房 近地铁 3200元/月",
            "price": 3200,
            "location": "宝安中心区",
            "room_type": "2室1厅",
            "tags": ["近地铁", "精装"],
            "link": "https://www.xiaohongshu.com/explore/test",
            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    ]


def main():
    """主函数"""
    try:
        print("=" * 50)
        print("小红书租房监控启动")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # 加载配置
        config = load_config()
        print(f"✓ 配置加载成功")
        print(f"  价格范围: {config['filters']['price_min']}-{config['filters']['price_max']}元/月")
        print(f"  房型: {config['filters']['room_type']}")
        
        # 爬取数据
        new_listings = scrape_xiaohongshu(config)
        print(f"✓ 爬取完成，获取 {len(new_listings)} 条数据")
        
        # 加载历史数据
        all_listings = load_listings()
        notified_ids = load_notified()
        
        # 筛选新房源
        from filter import filter_listings
        filtered = filter_listings(new_listings, config)
        print(f"✓ 筛选完成，符合条件 {len(filtered)} 条")
        
        # 找出未通知的新房源
        new_to_notify = [
            listing for listing in filtered
            if listing['id'] not in notified_ids
        ]
        
        if new_to_notify:
            print(f"✓ 发现 {len(new_to_notify)} 条新房源")
            
            # 发送通知
            from notifier import send_notifications
            send_notifications(new_to_notify, config)
            
            # 更新已通知列表
            notified_ids.extend([listing['id'] for listing in new_to_notify])
            save_notified(notified_ids)
        else:
            print("✓ 没有新房源")
        
        # 保存所有房源
        all_listings.extend(new_listings)
        save_listings(all_listings)
        
        print("=" * 50)
        print("监控完成")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
