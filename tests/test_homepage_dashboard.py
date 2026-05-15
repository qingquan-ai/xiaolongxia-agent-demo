import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _set_data_dir(path: Path) -> None:
    object.__setattr__(settings, "data_dir", path)


def _write_latest_report(data_dir: Path) -> None:
    payload = {
        "data_version": 1,
        "generated_at": "2026-05-15T09:30:00+08:00",
        "source": "feishu_event",
        "order_analysis": {
            "summary": {
                "total_orders": 5,
                "total_revenue": 742,
                "average_order_value": 148.4,
                "top_product": "十三香小龙虾",
                "peak_periods": ["午市", "晚市", "夜宵"],
            }
        },
        "reputation_analysis": {
            "summary": {
                "total_comments": 4,
                "negative_comments": 1,
                "risk_level": "medium",
                "risk_keywords": ["慢", "不够入味", "少"],
            }
        },
        "competitors": [
            {
                "name": "隔壁虾王",
                "platform": "美团",
                "promotion": "双人套餐",
                "hot_product": "蒜蓉小龙虾",
                "note": "夜宵时段折扣明显",
            },
            {
                "name": "老街龙虾",
                "platform": "大众点评",
                "promotion": "满100减20",
                "hot_product": "十三香小龙虾",
                "note": "午市套餐曝光高",
            }
        ],
        "report": {
            "agent": "写日报虾",
            "title": "今日小龙虾运营日报",
            "markdown": """# 今日小龙虾运营日报

## 经营概览
- 订单 36 单
- 销售额 4288 元

## 明日行动建议
- 【后厨】晚市提前备好十三香小龙虾
- 【前厅】先回复低分评价
- 【运营】观察周边套餐促销
""",
            "ai_mode": "OpenRouter",
            "OPENROUTER_MODEL": "DeepSeek",
        },
    }
    (data_dir / "latest_report.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_homepage_empty_state_does_not_generate_or_write(monkeypatch, tmp_path):
    client = TestClient(app)
    old_data_dir = settings.data_dir
    _set_data_dir(tmp_path)
    monkeypatch.setattr(
        "app.main.generate_daily_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("homepage must not generate reports")
        ),
    )
    monkeypatch.setattr(
        "app.main.save_latest_report_cache",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("homepage must not write latest report cache")
        ),
        raising=False,
    )

    try:
        response = client.get("/")
    finally:
        _set_data_dir(old_data_dir)

    assert response.status_code == 200
    assert "暂无日报，请在飞书群 @机器人 发送‘生成今日日报’。" in response.text
    assert not (tmp_path / "latest_report.json").exists()
    assert not (tmp_path / "report_history.json").exists()


def test_homepage_shows_customer_dashboard_without_technical_terms(tmp_path):
    client = TestClient(app)
    old_data_dir = settings.data_dir
    _set_data_dir(tmp_path)
    _write_latest_report(tmp_path)

    try:
        response = client.get("/")
    finally:
        _set_data_dir(old_data_dir)

    assert response.status_code == 200
    html = response.text
    assert "最新日报已生成" in html
    assert "最近一次日报" not in html
    assert "2026-05-15 09:30" in html
    assert "经营数据、舆情风险、竞品动态和明日行动已汇总。" in html
    assert "经营、舆情、竞品与明日建议已汇总" not in html
    assert "订单 / 评论 / 竞品信息已整理" not in html
    assert 'class="grid kpi-grid"' in html
    assert 'class="card kpi-card"' in html
    assert "今日订单" in html
    assert "5 单" in html
    assert "销售额 742 元" in html
    assert "客单价 148.4 元" in html
    assert "爆款产品" in html
    assert "十三香小龙虾" in html
    assert "继续作为主推" in html
    assert "舆情待处理" in html
    assert "1 条差评" in html
    assert "明日重点" in html
    assert "2 项行动" in html
    assert "晚市履约｜差评回复" in html
    assert "查看经营复盘" not in html
    assert "查看行动建议" not in html
    assert "午市 11:30-13:30｜晚市 17:30-20:00｜夜宵 21:00-23:30" not in html
    assert "<li>午市 11:30-13:30</li>" in html
    assert "<li>晚市 17:30-20:00</li>" in html
    assert "<li>夜宵 21:00-23:30</li>" in html
    assert html.count("今日经营复盘") == 1
    assert "经营诊断" in html
    assert "经营表现" in html
    assert "高峰时段" in html
    assert "风险问题" in html
    assert "明日行动清单" in html
    assert "今天收到 4 条评论，其中 1 条低分评价" in html
    assert "慢、不够入味、少" in html
    assert "建议今天先完成差评回复，并同步后厨复查。" in html
    assert "竞品观察" in html
    assert "竞品门店" in html
    assert "平台" in html
    assert "促销动作" in html
    assert "热卖品" in html
    assert "隔壁虾王" in html
    assert "老街龙虾" in html
    assert "<td>美团</td>" in html
    assert "<td>双人套餐</td>" in html
    assert "<td>蒜蓉小龙虾</td>" in html
    assert "竞品主要围绕套餐价格和爆款口味做促销，明日需重点关注套餐价格与夜宵时段竞争。" in html
    assert "明日行动建议" not in html
    assert 'class="checklist"' in html
    assert "晚市前 30 分钟完成备货和排班确认" in html
    assert "优先回复差评并记录问题原因" in html
    assert "继续主推十三香小龙虾" in html
    assert "观察竞品套餐和夜宵时段促销" in html
    assert "查看全部建议" not in html
    assert "日报正文摘要" not in html
    for forbidden in (
        "OpenRouter",
        "DeepSeek",
        "webhook",
        "feishu_event",
        "ai_mode",
        "llm_mode",
        "model",
        "OPENROUTER_MODEL",
    ):
        assert forbidden not in html
