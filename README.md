# 小红书租房监控

自动监控小红书深圳宝安地区租房信息，发现符合条件的新房源立即通知。

## 功能特性

- 🔍 自动爬取小红书租房帖子
- 💰 价格筛选（3000-3500元/月）
- 🏡 房型匹配（2室1厅）
- 🔔 新房源 Telegram 实时通知
- 🚫 智能去重，避免重复通知
- 🔁 关键词分组轮换，降低单次查询强度
- 🧠 持久化浏览器 profile，尽量保留真人浏览状态
- ⏰ 定时自动检查

## 配置说明

### 筛选条件

- **价格范围**: 3000-3500元/月
- **房型**: 2室1厅
- **地区**: 深圳宝安
- **排除**: 转租、短租、日租

### 优先标签

- 近地铁
- 精装修
- 独立卫浴

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置登录态（推荐优先用持久化 profile）

小红书现在更容易对搜索页做登录/验证拦截，**推荐优先使用持久化 profile**，而不是直接把 `.env` Cookie 强行注入到浏览器上下文里。

#### 推荐方案：持久化 profile

```bash
python scripts/open_profile.py
```

在弹出的浏览器里手动扫码、登录、过验证。完成后关闭窗口即可，后续抓取会复用同一份 `data/playwright-profile`。

#### 备选方案：`.env` Cookie 注入

只有在你明确想回退到 Cookie 模式时，再创建 `.env`：

```env
XHS_COOKIE=your_cookie_here
XHS_USE_ENV_COOKIE=true
```

> 注意：即使设置了 `XHS_COOKIE`，脚本现在也**默认不会自动注入**；只有显式设置 `XHS_USE_ENV_COOKIE=true` 才会启用，避免旧 Cookie 污染已经可用的持久化 profile。

### 3. 日常运行

当前更稳的方式仍然是默认可视模式：

```bash
python scripts/scraper.py --max-pages 1
```

如果你要测试后台无头运行，可以显式开启：

```bash
python scripts/scraper.py --headless --max-pages 1
```

> 实测无头模式在小红书搜索页更容易触发验证，因此目前推荐把 `--headless` 视为实验选项，而不是默认方案。

### 4. OpenClaw 一键运行摘要

如果是给 OpenClaw 会话调用，推荐直接运行：

```bash
python scripts/run_monitor_once.py --max-pages 1
```

它会：
- 执行一轮抓取
- 把本轮状态写入 `data/latest_run_summary.json`
- 在控制台输出一段适合直接转发给用户的摘要

### 3. 测试运行

```bash
python scripts/scraper.py
```

### 3.1 人工扫码/过验证（推荐）

```bash
python scripts/open_profile.py
```

这会打开持久化浏览器 profile。你可以在弹出的窗口里手动扫码、登录或过安全验证。完成后关闭窗口即可，后续抓取会复用同一份 profile。

### 4. 集成到 OpenClaw

将项目 clone 到 OpenClaw workspace：

```bash
cd ~/.openclaw/workspace/skills/
git clone https://github.com/hinschow/xiaohongshu-rental-monitor.git
```

添加 cron 任务（每小时检查）：

```javascript
{
  "name": "rental-monitor-hourly",
  "schedule": {
    "kind": "cron",
    "expr": "10 * * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "执行租房监控：运行 python scripts/scraper.py",
    "timeoutSeconds": 300
  }
}
```

## 项目结构

```
xiaohongshu-rental-monitor/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── defaults.json          # 筛选配置
├── scripts/
│   ├── scraper.py             # 爬虫主脚本
│   ├── filter.py              # 筛选逻辑
│   └── notifier.py            # 通知发送
├── data/
│   ├── listings.json          # 所有房源
│   ├── notified.json          # 已通知房源
│   └── .gitkeep
└── tests/
    └── test_scraper.py
```

## 通知格式

```
🏠 新房源提醒

📝 标题：宝安中心两房一厅房东直租
📄 摘要：近地铁，精装修，拎包入住...
📍 位置：宝安中心区
💰 价格：3200元/月
🏡 房型：2室1厅
📅 发布：2小时前

✨ 亮点：近地铁、精装修

🔗 链接：https://www.xiaohongshu.com/explore/xxxx
```

## OpenClaw 通知模式

本项目当前按 **OpenClaw 内发消息** 设计：

- 脚本负责抓取、筛选、格式化通知内容
- 通知内容打印到标准输出
- 由上层 OpenClaw 会话 / cron agent 读取并转发到当前聊天

因此**不需要**在项目里额外配置 Telegram Bot Token。

## 注意事项

### 反爬策略

- 使用 playwright 模拟真实浏览器
- 请求间隔 2-5 秒随机
- 每小时检查一次（避免频繁请求）
- 建议配置 Cookie

### 数据管理

- `listings.json` 保存所有历史房源
- `notified.json` 只保存已通知的房源 ID
- 自动清理 30 天前的数据

### 错误处理

- 网络超时自动重试 3 次
- 解析失败记录日志
- Cookie 失效发送告警

## 开发计划

- [ ] 基础爬虫实现
- [ ] 筛选逻辑
- [ ] Telegram 通知
- [ ] 去重机制
- [ ] Cookie 管理
- [ ] 错误重试
- [ ] 数据清理
- [ ] 单元测试

## License

MIT
