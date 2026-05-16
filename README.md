# 小龙虾 AI 自动运营中控台 Demo

一个最小可运行的 FastAPI Demo，用本地 JSON 数据模拟“小龙虾 AI 自动打工岗位”。

第一版包含：

- 首页 `/`
- 健康检查 `/health`
- FastAPI 文档 `/docs`
- 数据分析虾
- 舆情监控虾
- 写日报虾
- 模拟飞书 webhook：`POST /api/webhook/feishu`

第一版默认使用 mock 模式，不接真实大模型、不接真实飞书、不接数据库。

## 本地启动

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## 访问地址

- 首页：http://127.0.0.1:8000/
- 健康检查：http://127.0.0.1:8000/health
- 接口文档：http://127.0.0.1:8000/docs

## 测试模拟飞书 webhook

```bash
curl -X POST "http://127.0.0.1:8000/api/webhook/feishu" ^
  -H "Content-Type: application/json" ^
  -d "{\"event_id\":\"demo-001\",\"sender\":\"运营小王\",\"chat_id\":\"demo-chat\",\"text\":\"生成今日小龙虾运营日报\"}"
```

macOS / Linux:

```bash
curl -X POST "http://127.0.0.1:8000/api/webhook/feishu" \
  -H "Content-Type: application/json" \
  -d '{"event_id":"demo-001","sender":"运营小王","chat_id":"demo-chat","text":"生成今日小龙虾运营日报"}'
```

## 服务器定时生成日报

`POST /api/reports/daily` 用于服务器 crontab 定时触发日报生成和飞书推送。该接口会复用现有日报生成流程，生成日报后写入 `latest_report.json`、追加 `report_history.json`，并推送到飞书群。

生产环境建议在 `.env` 中配置：

```bash
CRON_SECRET=请替换为足够长的随机密钥
```

服务器上建议让 crontab 调用脚本，不要在 crontab 里直接写一长串 `curl`。脚本会从 `/root/xiaolongxia-agent-demo/.env` 读取 `CRON_SECRET`，并把执行日志写入 `/root/xiaolongxia-agent-demo/cron_daily_report.log`。

```bash
0 22 * * * /bin/bash /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
```

如果旧 crontab 里还有直接 `curl http://127.0.0.1:8000/api/reports/daily` 的任务，需要替换成上面的脚本调用，避免重复生成和重复推送。

手动检查脚本时可以运行：

```bash
/bin/bash /root/xiaolongxia-agent-demo/scripts/cron_daily_report.sh
tail -n 100 /root/xiaolongxia-agent-demo/cron_daily_report.log
```

生产环境必须配置 `CRON_SECRET`。脚本读取不到 `CRON_SECRET` 时会直接失败退出，不会继续请求接口。

## 说明

`.env` 已加入 `.gitignore`。如果后续接真实大模型，只能把 API Key 放进本地 `.env`，不要提交到代码仓库。
