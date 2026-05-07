"""Telegram channel posting via Bot API."""
import logging
import os
import time

import requests

log = logging.getLogger(__name__)


def send_message(text: str) -> bool:
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"].strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {
            "is_disabled": False,
            "prefer_large_media": True,
            "show_above_text": False,
        },
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            return True
        log.error("Telegram %s: %s", r.status_code, r.text)
        return False
    except Exception as e:
        log.exception("Telegram send failed: %s", e)
        return False


def post_items(items: list[dict]) -> list[dict]:
    """Send each item's pre-rendered post_text. Return successfully posted."""
    sent: list[dict] = []
    for it in items:
        text = it.get("post_text") or ""
        if not text:
            log.warning("No post_text for %s, skipping", it.get("url"))
            continue
        if send_message(text):
            sent.append(it)
            time.sleep(1.5)
        else:
            log.warning("Failed to post: %s", it.get("url"))
    return sent
