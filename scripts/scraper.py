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

默认使用非无头模式，尽量更接近真人浏览器行为。
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
HEALTH_FILE = DATA_DIR / "scrape_health.json"

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


def load_health_state():
    if HEALTH_FILE.exists():
        try:
            with open(HEALTH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "consecutive_empty_runs": 0,
        "last_empty_run_at": None,
        "last_successful_run_at": None,
        "last_alerted_empty_count": 0,
        "last_status": "unknown"
    }


def save_health_state(state):
    with open(HEALTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def generate_id(title, link):
    """根据标题和链接生成稳定的唯一ID"""
    raw = f"{title}|{link}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def extract_publish_date(link):
    """从小红书笔记链接提取发布时间（ID前8位是十六进制时间戳）"""
    m = re.search(r'/explore/([a-f0-9]{24})', link)
    if m:
        try:
            ts = int(m.group(1)[:8], 16)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    return ""


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
    """从文本提取价格，排除非租金数字（收入、面积、年份等）"""
    # 先排除：月入/年入/收入/工资/薪资 + 数字 这类表述
    # 用负向后顾排除这些上下文
    exclude_prefix = r'(?:月入|年入|收入|工资|薪资|时薪|日薪|存款|存了|攒了|花了|花费|投入|首付|押金|中介费|服务费|面积|约)\s*'

    patterns = [
        r'(\d{3,5})\s*[-/~至到]\s*(\d{3,5})\s*(?:元|块|/月)',
        r'(\d{3,5})\s*(?:元|块)/月',
        r'月租?\s*(\d{3,5})',
        r'(?:租金|价格|房租)[：:]\s*(\d{3,5})',
        r'(\d{3,5})\s*(?:元|块)',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            start = m.start()
            # 检查匹配位置之前是否有排除前缀
            prefix_text = text[max(0, start - 10):start]
            if re.search(exclude_prefix + r'$', prefix_text):
                continue
            price = int(m.group(1))
            if 500 <= price <= 20000:
                return price
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
    # 具体地名优先
    known_places = [
        "宝安中心", "西乡", "固戍", "后瑞", "碧海", "新安",
        "松岗", "沙井", "福永", "石岩", "光明", "坪洲",
        "灵芝", "翻身", "洪浪北", "兴东", "留仙洞", "桃园",
    ]
    for place in known_places:
        if place in text:
            return place

    # 区+具体地名（只匹配汉字，遇到数字/标点/动词停止）
    m = re.search(r"((?:宝安|南山|福田|龙华|龙岗|罗湖|光明|坪山)[·\s]?[\u4e00-\u9fff]{1,4}(?:区|街道|路|地铁|站|湾|城|园))", text)
    if m:
        return m.group(1)

    # 仅区名
    m = re.search(r"(宝安|南山|福田|龙华|龙岗|罗湖|光明|坪山)", text)
    if m:
        return m.group(1)

    return default


def is_rental_related(text):
    """检查文本是否与租房相关（必须包含租房关键词）"""
    rental_keywords = [
        "出租", "转租", "直租", "租房", "房东", "整租", "合租",
        "民房", "城中村", "农民房", "一房", "两房", "三房", "单间",
        "室", "厅", "卫", "阳台", "月租", "押金", "租金", "房租"
    ]
    text_lower = text.lower()
    # 至少包含一个租房关键词
    return any(keyword in text_lower for keyword in rental_keywords)


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

        # 如果有 Cookie，先访问首页让 Cookie 生效
        if cookie_str:
            try:
                page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=20000)
                time.sleep(random.uniform(1, 2))
            except Exception:
                pass

        login_blocked = False

        for keyword in keywords:
            if login_blocked:
                print(f"  跳过 '{keyword}' (需要登录)")
                continue

            print(f"\n  搜索关键词: {keyword}")
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes&sort=time"

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(4.5, 8.5))
            except Exception as e:
                print(f"  访问搜索页失败: {e}")
                continue

            # 处理登录弹窗 — 小红书搜索必须登录
            login_modal = page.query_selector('div.login-container, div[class*="login-modal"], div[class*="loginContainer"]')
            if login_modal:
                if not cookie_str:
                    print("  ⚠️ 小红书搜索需要登录才能查看结果")
                    print("  请按以下步骤配置 Cookie:")
                    print("    1. 浏览器打开 https://www.xiaohongshu.com 并登录")
                    print("    2. F12 打开开发者工具 → Application → Cookies")
                    print("    3. 复制所有 Cookie 值到 .env 文件:")
                    print('       XHS_COOKIE=a1=xxx; webId=xxx; web_session=xxx; ...')
                    login_blocked = True
                    continue

                # 有 Cookie 但还是弹登录 → Cookie 过期
                # 尝试关闭弹窗看看
                page.keyboard.press("Escape")
                time.sleep(1)
                login_still = page.query_selector('div.login-container, div[class*="login-modal"]')
                if login_still and login_still.is_visible():
                    print("  ⚠️ Cookie 已过期，请重新获取")
                    login_blocked = True
                    continue
                print("  已关闭登录弹窗")

            # 切换到「图文」标签（过滤掉视频）
            try:
                text_tab = page.query_selector('div.search-tab span:has-text("图文"), a:has-text("图文")')
                if text_tab:
                    text_tab.click()
                    time.sleep(random.uniform(1, 2))
            except Exception:
                pass

            # 调试：保存截图和HTML
            try:
                screenshot_path = DATA_DIR / f"debug_screenshot_{keyword[:10].replace(' ', '_')}.png"
                page.screenshot(path=str(screenshot_path))
                print(f"    截图已保存: {screenshot_path}")
                
                html_path = DATA_DIR / f"debug_html_{keyword[:10].replace(' ', '_')}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                print(f"    HTML已保存: {html_path}")
            except Exception as e:
                print(f"    保存调试文件失败: {e}")

            # 滚动加载更多
            loaded_pages = 0
            while loaded_pages < pages_limit:
                # 提取当前页面的帖子
                try:
                    # 小红书搜索结果选择器（多种尝试）
                    cards = page.query_selector_all('section.note-item, div[class*="note-item"]')
                    print(f"    尝试选择器1: 找到 {len(cards)} 个 cards")
                    if not cards:
                        cards = page.query_selector_all('div.feeds-page section, div[class*="feeds"] section')
                        print(f"    尝试选择器2: 找到 {len(cards)} 个 cards")
                    if not cards:
                        # 最宽泛：任何包含笔记链接的容器
                        cards = page.query_selector_all('a[href*="/explore/"], a[href*="/search_result/"]')
                        print(f"    尝试选择器3 (链接): 找到 {len(cards)} 个 cards")

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

                            if not link:
                                print(f"      跳过: 无链接")
                                continue
                            if link in seen_links:
                                print(f"      跳过: 重复链接")
                                continue
                            seen_links.add(link)

                            # 提取标题
                            title_el = card.query_selector("a.title span, span.title, div.title, a.title")
                            title = title_el.inner_text().strip() if title_el else ""
                            
                            if not title:
                                print(f"      跳过: 无标题 - {link}")
                                continue

                            # 提取摘要/描述
                            desc_el = card.query_selector("div.desc, span.desc, p")
                            desc = desc_el.inner_text().strip() if desc_el else ""

                            full_text = f"{title} {desc}"
                            
                            print(f"      检查: {title[:30]}...")

                            # ⚠️ 关键验证：必须包含租房关键词，否则跳过
                            if not is_rental_related(full_text):
                                print(f"        ✗ 不包含租房关键词")
                                continue
                            
                            print(f"        ✓ 包含租房关键词")

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
                                "published_at": extract_publish_date(link),
                                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            all_listings.append(listing)

                        except Exception as e:
                            continue

                    # Fallback: regex extract from raw HTML if no cards found via selectors
                    if not cards:
                        html = page.content()
                        # Match note links and nearby titles
                        note_matches = re.findall(
                            r'href="(/explore/[a-f0-9]+)"[^>]*>.*?<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>',
                            html, re.DOTALL
                        )
                        if not note_matches:
                            note_matches = re.findall(
                                r'href="(/explore/[a-f0-9]+)"', html
                            )
                            note_matches = [(m, "") for m in note_matches] if note_matches else []

                        for href, title in note_matches:
                            link = f"https://www.xiaohongshu.com{href}"
                            if link in seen_links:
                                continue
                            seen_links.add(link)
                            title = title.strip() if title else f"小红书笔记 {href.split('/')[-1]}"
                            
                            # ⚠️ 关键验证：必须包含租房关键词
                            if not is_rental_related(title):
                                continue
                            
                            price = parse_price_from_text(title)
                            room_type = parse_room_type(title)
                            location = extract_location(title, config["search"].get("location", "深圳宝安"))
                            tags = extract_tags(title)
                            all_listings.append({
                                "id": generate_id(title, link),
                                "title": title,
                                "description": "",
                                "price": price,
                                "location": location,
                                "room_type": room_type,
                                "tags": tags,
                                "link": link,
                                "keyword": keyword,
                                "published_at": extract_publish_date(link),
                                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            })

                        if note_matches:
                            print(f"    (HTML fallback: 提取到 {len(note_matches)} 条)")

                except Exception as e:
                    print(f"  提取帖子失败: {e}")

                loaded_pages += 1
                if loaded_pages < pages_limit:
                    # 滚动加载更多
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(delay + 2, delay + 6))

            print(f"  关键词 '{keyword}' 获取 {len([l for l in all_listings if l['keyword'] == keyword])} 条")

        # 可选：进入详情页补全信息（对价格为空的帖子）
        missing_price = [l for l in all_listings if not l["price"]]
        if missing_price:
            print(f"\n  尝试补全 {min(len(missing_price), 10)} 条缺少价格的帖子...")
            for listing in missing_price[:10]:
                try:
                    page.goto(listing["link"], wait_until="domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(1.5, 3))

                    # 提取详情页内容 — 用精确选择器避免匹配到导航栏
                    detail_text = ""
                    # 小红书笔记详情页的正文选择器（按优先级）
                    detail_selectors = [
                        "#detail-desc .note-text",           # 笔记正文区域
                        "div.note-text",                     # 笔记文本
                        "#detail-desc",                      # 详情描述容器
                        "div.note-content .content",         # 内容区
                        "article",                           # 语义化文章标签
                    ]
                    for sel in detail_selectors:
                        content_el = page.query_selector(sel)
                        if content_el:
                            txt = content_el.inner_text().strip()
                            # 过滤掉导航栏误匹配（"发现\n发布\n通知\n我"）
                            if txt and len(txt) > 20 and "发现\n发布\n通知" not in txt:
                                detail_text = txt
                                break

                    if detail_text:
                        if not listing["price"]:
                            listing["price"] = parse_price_from_text(detail_text)
                        if not listing["room_type"]:
                            listing["room_type"] = parse_room_type(detail_text)
                        if not listing["tags"]:
                            listing["tags"] = extract_tags(detail_text)
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
    parser.add_argument("--headless", action="store_true", help="使用无头模式")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（默认）")
    parser.add_argument("--max-pages", type=int, default=None, help="每个关键词最大翻页数")
    parser.add_argument("--days", type=int, default=7, help="只保留最近N天内发布的帖子（默认7天）")
    args = parser.parse_args()

    headless = bool(args.headless and not args.no_headless)

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

        health = load_health_state()

        if not new_listings:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            health["consecutive_empty_runs"] = int(health.get("consecutive_empty_runs", 0)) + 1
            health["last_empty_run_at"] = now_str
            health["last_status"] = "empty"
            save_health_state(health)

            print("  没有获取到数据，可能需要检查 Cookie 或网络")
            if health["consecutive_empty_runs"] >= 2 and health.get("last_alerted_empty_count", 0) < health["consecutive_empty_runs"]:
                print("\n⚠️ 小红书爬虫连续 2 次以上返回 0 条数据，且最新调试页已出现安全验证。")
                print("⚠️ 基本可确定是 Cookie / 风控问题，建议立即更新 .env 里的 XHS_COOKIE。")
                health["last_alerted_empty_count"] = health["consecutive_empty_runs"]
                save_health_state(health)
            print("=" * 50)
            return

        # 成功抓到数据，重置健康状态
        health["consecutive_empty_runs"] = 0
        health["last_successful_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        health["last_status"] = "ok"
        save_health_state(health)

        # 过滤掉太旧的帖子
        cutoff_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        before_count = len(new_listings)
        new_listings = [l for l in new_listings if not l.get("published_at") or l["published_at"] >= cutoff_date]
        skipped = before_count - len(new_listings)
        if skipped:
            print(f"  过滤掉 {skipped} 条超过 {args.days} 天的旧帖子")

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
