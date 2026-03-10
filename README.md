# 小红书租房监控

自动监控小红书深圳宝安地区租房信息，发现符合条件的新房源立即通知。

## 功能特性

- 🔍 自动爬取小红书租房帖子
- 💰 价格筛选（3000-3500元/月）
- 🏡 房型匹配（2室1厅）
- 🔔 新房源 Telegram 实时通知
- 🚫 智能去重，避免重复通知
- ⏰ 每小时自动检查

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

### 2. 配置 Cookie（可选）

小红书可能需要登录才能访问完整内容：

1. 浏览器登录小红书
2. 打开开发者工具 (F12)
3. 复制 Cookie
4. 创建 `.env` 文件：

```env
XHS_COOKIE=your_cookie_here
```

### 3. 测试运行

```bash
python scripts/scraper.py
```

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

📍 位置：宝安中心区
💰 价格：3200元/月
🏡 房型：2室1厅
📅 发布：2小时前

✨ 亮点：近地铁、精装修

🔗 查看详情：[小红书链接]
```

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
