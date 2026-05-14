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

## 说明

`.env` 已加入 `.gitignore`。如果后续接真实大模型，只能把 API Key 放进本地 `.env`，不要提交到代码仓库。
