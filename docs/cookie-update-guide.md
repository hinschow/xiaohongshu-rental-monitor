# 小红书 Cookie 更新指南

## 为什么需要更新 Cookie？

小红书搜索页面现在要求扫码验证身份，说明当前 Cookie 已失效或被风控。

## 如何获取新的 Cookie

### 方法 1：浏览器手动获取（推荐）

1. **打开浏览器无痕模式**（避免干扰）
   - Chrome: `Ctrl + Shift + N`
   - Edge: `Ctrl + Shift + P`

2. **访问小红书并登录**
   ```
   https://www.xiaohongshu.com
   ```

3. **登录后，进行一次搜索**
   - 搜索任意关键词（如"深圳租房"）
   - 确保能看到搜索结果（不是扫码页面）

4. **打开开发者工具**
   - 按 `F12` 或 `Ctrl + Shift + I`

5. **获取 Cookie**
   - 点击 `Application` 标签（或 `存储`）
   - 左侧选择 `Cookies` → `https://www.xiaohongshu.com`
   - 复制所有 Cookie 值

6. **格式化 Cookie**
   - 将 Cookie 格式化为：`name1=value1; name2=value2; ...`
   - 重点关注这些字段：
     - `a1`
     - `webId`
     - `web_session`
     - `xsecappid`
     - `websectiga`

### 方法 2：使用脚本自动获取

```javascript
// 在小红书页面的控制台运行
copy(document.cookie)
```

然后粘贴到 `.env` 文件。

## 更新 .env 文件

打开 `C:\Users\Hins\.openclaw\workspace\xiaohongshu-rental-monitor\.env`

替换 `XHS_COOKIE` 的值：

```env
XHS_COOKIE=a1=xxx; webId=xxx; web_session=xxx; xsecappid=xxx; websectiga=xxx; ...
```

## 验证 Cookie 是否有效

运行测试命令：

```bash
cd C:\Users\Hins\.openclaw\workspace\xiaohongshu-rental-monitor
python scripts/scraper.py --max-pages 1 --no-headless
```

如果看到浏览器打开并成功加载搜索结果（不是扫码页面），说明 Cookie 有效。

## 常见问题

### Q: Cookie 多久会过期？
A: 通常 7-30 天，取决于小红书的策略。

### Q: 为什么获取 Cookie 后还是要扫码？
A: 可能原因：
1. Cookie 复制不完整
2. 浏览器环境差异（User-Agent、指纹）
3. IP 被风控

### Q: 如何避免频繁更新 Cookie？
A: 
1. 降低爬取频率（目前是每小时一次）
2. 使用代理 IP 轮换
3. 模拟真实用户行为（随机延迟、滚动）

## 高级：使用 Playwright 持久化登录

如果频繁过期，可以考虑使用 Playwright 的持久化上下文：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir="./user_data",  # 保存登录状态
        headless=False
    )
    # 首次运行时手动登录，之后会自动保持登录
```

这样只需要登录一次，后续会自动保持登录状态。
