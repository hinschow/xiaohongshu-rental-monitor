#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书租房信息爬虫

使用 Playwright 模拟浏览器访问小红书搜索页，提取租房帖子信息。
支持 Cookie 登录、随机延迟反爬、去重、30天数据清理。

Usage:
    python scripts/scraper.py
    python scripts/scraper.py --headless
    python scripts/scraper.py --max-pages 3
"""

import sys
import io
import json
import time
import random
import re
import os
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote

# 强制 UTF-8 编码
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config" / "defaults.json"
DATA_DIR = ROOT_DIR / "data"
LISTINGS_FILE = DATA_DIR / "listings.json"
NOTIFIED_FILE = DATA_DIR / "notified.json"

DATA_DIR.mkdir(exist_ok=True)

# 数据保留天数
RETENTION_DAYS = 30


def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_listings():
    if LISTINGS_FILE.exists():
        with open(LISTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_listings(listings):
    with open(LISTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)


def load_notified():
    if NOTIFIED_FILE.exists():
        with open(NOTIFIED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_notified(notified_ids):
    with open(NOTIFIED_FILE, 'w', encoding='utf-8') as f:
        json.dump(notified_ids, f, ensure_ascii=False, indent=2)


def generate_id(title, link):
    """根据标题和链接生成稳定的唯一ID"""
    raw = f"{title}|{link}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def clean_old_data(listings, days=RETENTION_DAYS):
    """清理超过指定天数的旧数据"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    before = len(listings)
    listings = [l for l in listings if l.get("scraped_at", "") >= cutoff]
    removed = before - len(listings)
    if removed > 0:
        print(f"  清理了 {removed} 条超过 {days} 天的旧数据")
    return listings


def parse_price_from_text(text):
    """从文本提取价格"""
    patterns = [
        r'(\d{3,5})\s*[-/~至到]\s*(\d{3,5})\s*(?:元|块|/月)',
        r'(\d{3,5})\s*(?:元|块)/月',
        r'月租?\s*(\d{3,5})',
        r'(\d{3,5})\s*(?:元|块)',
        r'(?:租金|价格|房租)[：:]\s*(\d{3,5})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return int(m.group(1))
    return None


def parse_room_type(text):
    """从文本提取房型"""
    patterns = [
        (r'(\d)\s*室\s*(\d)\s*厅', lambda m: f"{m.group(1)}室{m.group(2)}厅"),
        (r'(\d)\s*房\s*(\d)\s*厅', lambda m: f"{m.group(1)}室{m.group(2)}厅"),
        (r'(一|二|三|四)\s*室\s*(一|二)\s*厅', lambda m: f"{'一二三四'.index(m.group(1))+1}室{'一二'.index(m.group(2))+1}厅"),
        (r'(一|两|二|三|四)\s*房\s*(一|二)\s*厅', lambda m: f"{'一两二三四'.index(m.group(1))+1}室{'一二'.index(m.group(2))+1}厅" if m.group(1) != '两' else f"2室{'一二'.index(m.group(2))+1}厅"),
        (r'两室一厅', lambda m: "2室1厅"),
        (r'两房一厅', lambda m: "2室1厅"),
        (r'单间', lambda m: "单间"),
        (r'开间', lambda m: "开间"),
    ]
    for p, fmt in patterns:
        m = re.search(p, text)
        if m:
            return fmt(m)
    return None


def extract_tags(text):
    """从文本提取标签"""
    tag_patterns = {
        "近地铁": r"近地铁|地铁\s*\d|地铁口",
        "精装修": r"精装|豪装|拎包入住",
        "独立卫浴": r"独立卫|独卫|独立洗手间",
        "有阳台": r"阳台|飘窗",
        "南向": r"朝南|南向|南北通透",
        "电梯房": r"电梯房|电梯",
        "停车位": r"停车|车位",
        "家电齐全": r"家电齐|家电全|冰箱.*洗衣机|洗衣机.*冰箱",
    }
    tags = []
    for tag, pattern in tag_patterns.items():
        if re.search(pattern, text):
            tags.append(tag)
    return tags


def extract_location(text, default="深圳宝安"):
    """从文本提取位置"""
    location_patterns = [
        r"(宝安\S{1,6}(?:区|街道|路|地铁))",
        r"(宝安中心|西乡|固戍|后瑞|碧海|新安|松岗|沙井|福永|石岩|光明)",
        r"((?:宝安|南山|福田|龙华)\S{0,4})",
    ]
    for p in location_patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return default


def scrape_xiaohongshu(config, headless=True, max_pages=None):
    """
    使用 Playwright 爬取小红书租房信息。

    流程：
    1. 启动浏览器，设置 Cookie（如有）
    2. 依次搜索每个关键词
    3. 滚动加载更多结果
    4. 提取帖子标题、链接、摘要
    5. 点击进入详情页提取价格、房型等（可选）
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误: 请安装 playwright: pip install playwright && python -m playwright install chromium")
        return []

    keywords = config["search"]["keywords"]
    scraper_config = config.get("scraper", {})
    pages_limit = max_pages or scraper_config.get("max_pages", 5)
    delay = scraper_config.get("delay_seconds", 2)
    cookie_str = os.getenv("XHS_COOKIE", "")

    all_listings = []
    seen_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=scraper_config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )

        # 注入 Cookie
        if cookie_str:
            cookies = []
            for item in cookie_str.split(";"):
                item = item.strip()
                if "=" in item:
                    name, value = item.split("=", 1)
                    cookies.append({
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": ".xiaohongshu.com",
                        "path": "/",
                    })
            if cookies:
                context.add_cookies(cookies)
                print(f"  已注入 {len(cookies)} 个 Cookie")

        page = context.new_page()

        for keyword in keywords:
            print(f"\n  搜索关键词: {keyword}")
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                print(f"  访问搜索页失败: {e}")
                continue

            # 滚动加载更多
            loaded_pages = 0
            while loaded_pages < pages_limit:
                # 提取当前页面的帖子
                try:
                    # 小红书搜索结果的帖子容器
                    cards = page.query_selector_all('section.note-item, div[class*="note-item"], a[class*="cover"]')
                    if not cards:
                        # 备用选择器
                        cards = page.query_selector_all('div[data-v-a264b01a], div.feeds-page section')

                    for card in cards:
                        try:
                            # 提取链接
                            link_el = card.query_selector("a[href*='/explore/'], a[href*='/discovery/item/']")
                            if not link_el:
                                link_el = card if card.get_attribute("href") else None

                            link = ""
                            if link_el:
                                href = link_el.get_attribute("href") or ""
                                if href.startswith("/"):
                                    link = f"https://www.xiaohongshu.com{href}"
                                elif href.startswith("http"):
                                    link = href

                            if not link or link in seen_links:
                                continue
                            seen_links.add(link)

                            # 提取标题
                            title_el = card.query_selector("a.title span, span.title, div.title, a.title")
                            title = title_el.inner_text().strip() if title_el else ""

                            # 提取摘要/描述
                            desc_el = card.query_selector("div.desc, span.desc, p")
                            desc = desc_el.inner_text().strip() if desc_el else ""

                            full_text = f"{title} {desc}"
                            if not title:
                                continue

                            # 解析结构化字段
                            price = parse_price_from_text(full_text)
                            room_type = parse_room_type(full_text)
                            location = extract_location(full_text, config["search"].get("location", "深圳宝安"))
                            tags = extract_tags(full_text)

                            listing = {
                                "id": generate_id(title, link),
                                "title": title,
                                "description": desc,
                                "price": price,
                                "location": location,
                                "room_type": room_type,
                                "tags": tags,
                                "link": link,
                                "keyword": keyword,
                                "published_at": "",
                                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            all_listings.append(listing)

                        except Exception as e:
                            continue

                except Exception as e:
                    print(f"  提取帖子失败: {e}")

                loaded_pages += 1
                if loaded_pages < pages_limit:
                    # 滚动加载更多
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(delay, delay + 3))

            print(f"  关键词 '{keyword}' 获取 {len([l for l in all_listings if l['keyword'] == keyword])} 条")

        # 可选：进入详情页补全信息（对价格为空的帖子）
        missing_price = [l for l in all_listings if not l["price"]]
        if missing_price:
            print(f"\n  尝试补全 {min(len(missing_price), 10)} 条缺少价格的帖子...")
            for listing in missing_price[:10]:
                try:
                    page.goto(listing["link"], wait_until="domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(1.5, 3))

                    # 提取详情页内容
                    content_el = page.query_selector("div.note-content, div#detail-desc, div[class*='content']")
                    if content_el:
                        detail_text = content_el.inner_text().strip()
                        if not listing["price"]:
                            listing["price"] = parse_price_from_text(detail_text)
                        if not listing["room_type"]:
                            listing["room_type"] = parse_room_type(detail_text)
                        if not listing["tags"]:
                            listing["tags"] = extract_tags(detail_text)
                        # 保存详情页文本
                        listing["detail_text"] = detail_text[:2000]
                except Exception:
                    continue

        browser.close()

    print(f"\n  总计获取 {len(all_listings)} 条帖子")
    return all_listings


def merge_listings(existing, new_listings):
    """合并房源，按 id 去重，保留最新版本"""
    by_id = {l["id"]: l for l in existing}
    added = 0
    for l in new_listings:
        if l["id"] not in by_id:
            added += 1
        by_id[l["id"]] = l
    print(f"  合并: {len(existing)} 已有 + {added} 新增 = {len(by_id)} 总计")
    return list(by_id.values())


def main():
    parser = argparse.ArgumentParser(description="小红书租房爬虫")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式（默认）")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--max-pages", type=int, default=None, help="每个关键词最大翻页数")
    args = parser.parse_args()

    headless = not args.no_headless

    try:
        print("=" * 50)
        print("小红书租房监控启动")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        config = load_config()
        print(f"✓ 配置加载成功")
        print(f"  价格范围: {config['filters']['price_min']}-{config['filters']['price_max']}元/月")
        print(f"  房型: {config['filters']['room_type']}")
        print(f"  关键词: {', '.join(config['search']['keywords'])}")

        # 爬取数据
        new_listings = scrape_xiaohongshu(config, headless=headless, max_pages=args.max_pages)
        print(f"✓ 爬取完成，获取 {len(new_listings)} 条数据")

        if not new_listings:
            print("  没有获取到数据，可能需要检查 Cookie 或网络")
            print("=" * 50)
            return

        # 加载历史数据并去重合并
        all_listings = load_listings()
        notified_ids = load_notified()

        all_listings = merge_listings(all_listings, new_listings)

        # 清理旧数据
        all_listings = clean_old_data(all_listings)

        # 筛选
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

            from notifier import send_notifications
            send_notifications(new_to_notify, config)

            notified_ids.extend([listing['id'] for listing in new_to_notify])
            # 去重 notified_ids
            notified_ids = list(set(notified_ids))
            save_notified(notified_ids)
        else:
            print("✓ 没有新房源")

        # 保存
        save_listings(all_listings)

        print("=" * 50)
        print(f"监控完成 · 总房源 {len(all_listings)} · 本次筛出 {len(filtered)} · 新通知 {len(new_to_notify)}")
        print("=" * 50)

    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
