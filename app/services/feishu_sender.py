import base64
import hashlib
import hmac
import logging
import os
import time

import httpx


logger = logging.getLogger(__name__)

FEISHU_SEND_TIMEOUT_SECONDS = 10.0


def _build_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    return base64.b64encode(
        hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")


def send_feishu_text(text: str) -> bool:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    secret = os.getenv("FEISHU_SECRET", "").strip()

    if not webhook_url:
        logger.info("Feishu sender skipped reason=missing_webhook_url")
        return False

    body = {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }
    if secret:
        timestamp = str(int(time.time()))
        body["timestamp"] = timestamp
        body["sign"] = _build_sign(timestamp, secret)

    try:
        response = httpx.post(
            webhook_url,
            json=body,
            timeout=FEISHU_SEND_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        logger.warning(
            "Feishu sender failed fallback=skip reason=timeout timeout_seconds=%s",
            FEISHU_SEND_TIMEOUT_SECONDS,
        )
        return False
    except httpx.RequestError as exc:
        logger.warning(
            "Feishu sender failed fallback=skip reason=request_error error_type=%s",
            exc.__class__.__name__,
        )
        return False

    if response.status_code != 200:
        logger.warning(
            "Feishu sender failed fallback=skip reason=http_status status_code=%s",
            response.status_code,
        )
        return False

    try:
        response_body = response.json()
    except ValueError:
        logger.warning("Feishu sender failed fallback=skip reason=invalid_json")
        return False
    if not isinstance(response_body, dict):
        logger.warning("Feishu sender failed fallback=skip reason=invalid_body")
        return False

    code = response_body.get("code")
    if code != 0:
        logger.warning(
            "Feishu sender failed fallback=skip reason=feishu_code code=%s",
            code,
        )
        return False

    logger.info("Feishu sender succeeded msg_type=text")
    return True
