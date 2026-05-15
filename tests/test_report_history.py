import json
from pathlib import Path

from app.core.config import settings
from app.services import json_store
from app.services.feishu_adapter import generate_and_push_daily_report


def _set_data_dir(path: Path) -> None:
    object.__setattr__(settings, "data_dir", path)


def _sample_report(index: int = 1) -> dict:
    return {
        "source": f"test-{index}",
        "generated_at": f"2026-05-15T09:{index:02d}:00+08:00",
        "order_analysis": {
            "summary": {
                "total_orders": index,
                "total_revenue": index * 100,
                "average_order_value": 100,
                "top_product": "十三香小龙虾",
                "peak_periods": ["晚市"],
            }
        },
        "reputation_analysis": {
            "summary": {
                "total_comments": 4,
                "negative_comments": 1,
                "risk_level": "medium",
                "risk_keywords": ["慢", "不够入味"],
            }
        },
        "competitors": [
            {
                "name": "隔壁虾王",
                "platform": "美团",
                "promotion": "双人套餐",
                "hot_product": "蒜蓉小龙虾",
            }
        ],
        "report": {
            "agent": "写日报虾",
            "title": "今日小龙虾运营日报",
            "markdown": "## 明日行动建议\n- 晚市提前备货\n",
            "ai_mode": "mock",
        },
    }


def _write_demo_data(data_dir: Path) -> None:
    (data_dir / "orders.json").write_text(
        json.dumps(
            [
                {
                    "order_id": "O1",
                    "store": "小龙虾人民广场店",
                    "channel": "美团",
                    "product": "十三香小龙虾",
                    "quantity": 2,
                    "amount": 176,
                    "order_time": "2026-05-15 18:30:00",
                    "status": "completed",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "comments.json").write_text(
        json.dumps(
            [
                {
                    "comment_id": "C1",
                    "platform": "大众点评",
                    "store": "小龙虾人民广场店",
                    "rating": 2,
                    "content": "出餐慢，味道不够入味",
                    "created_at": "2026-05-15 19:20:00",
                    "replied": False,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "competitors.json").write_text(
        json.dumps(
            [
                {
                    "name": "隔壁虾王",
                    "platform": "美团",
                    "promotion": "双人套餐",
                    "hot_product": "蒜蓉小龙虾",
                    "note": "晚市折扣明显",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_report_history_is_created_when_missing(tmp_path):
    old_data_dir = settings.data_dir
    _set_data_dir(tmp_path)
    try:
        assert json_store.append_report_history(**_sample_report()) is True
    finally:
        _set_data_dir(old_data_dir)

    history_path = tmp_path / "report_history.json"
    assert history_path.exists()
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["source"] == "test-1"


def test_report_history_keeps_latest_20_records(tmp_path):
    old_data_dir = settings.data_dir
    _set_data_dir(tmp_path)
    try:
        for index in range(21):
            assert json_store.append_report_history(**_sample_report(index)) is True
    finally:
        _set_data_dir(old_data_dir)

    history = json.loads((tmp_path / "report_history.json").read_text(encoding="utf-8"))
    assert len(history) == 20
    assert history[0]["source"] == "test-20"
    assert history[-1]["source"] == "test-1"


def test_corrupt_report_history_does_not_block_daily_report_generation(
    monkeypatch,
    tmp_path,
):
    old_data_dir = settings.data_dir
    _set_data_dir(tmp_path)
    _write_demo_data(tmp_path)
    (tmp_path / "report_history.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr("app.services.feishu_adapter.send_feishu_text", lambda text: True)
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_daily_report",
        lambda *_args: _sample_report()["report"],
    )

    try:
        result = generate_and_push_daily_report(source="feishu_webhook")
    finally:
        _set_data_dir(old_data_dir)

    assert result["title"] == "今日小龙虾运营日报"
    latest = json.loads((tmp_path / "latest_report.json").read_text(encoding="utf-8"))
    history = json.loads((tmp_path / "report_history.json").read_text(encoding="utf-8"))
    assert latest["source"] == "feishu_webhook"
    assert len(history) == 1
    assert history[0]["source"] == "feishu_webhook"
