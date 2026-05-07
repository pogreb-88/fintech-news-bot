"""Telegram channel posting via Bot API (no library needed)."""
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

CATEGORY_LABEL = {
    "crypto": "Crypto/VASP",
    "payments": "Payments",
    "gambling": "Gambling/iGaming",
    "adult_psp": "High-Risk PSP",
    "sanctions": "Sanctions",
    "aml": "AML",
    "regulator_action": "Regulator",
    "other": "Other",
}

IMPORTANCE_DOT = {5: "🔴", 4: "🟠", 3: "🟡", 2: "🔵", 1: "⚪️"}


def _esc(s: str) -> str:
    """Escape HTML special chars for Telegram parse_mode=HTML."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def format_post(item: dict) -> str:
    dot = IMPORTANCE_DOT.get(int(item.get("importance", 0)), "⚪️")
    cat = CATEGORY_LABEL.get(item.get("category", "other"), "Other")
    headline = _esc(item.get("english_headline", item.get("title", "")))
    summary = _esc(item.get("russian_summary", "").strip())

    verified_line = (
        "✅ Подтверждено" if item.get("verified")
        else "⚠️ Не подтверждено (один источник)"
    )

    sources = item.get("supporting_sources") or [
        {"name": item.get("source_name", ""), "url": item.get("url", "")}
    ]
    src_links = " | ".join(
        f'<a href="{_esc(s["url"])}">{_esc(s["name"])}</a>' for s in sources
    )

    tag_cat = item.get("category", "other").replace("_", "")
    hashtags = f"#{tag_cat}"

    return (
        f"{dot} <b>[{cat}]</b> {headline}\n\n"
        f"{summary}\n\n"
        f"{verified_line}\n"
        f"🔗 {src_links}\n\n"
        f"{hashtags}"
    )


def send_message(text: str) -> bool:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "link_preview_options": {"is_disabled": False, "prefer_small_media": True},
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
    """Send items in order, return successfully posted."""
    sent: list[dict] = []
    for it in items:
        text = format_post(it)
        if send_message(text):
            sent.append(it)
            time.sleep(1.5)  # respect Telegram rate limits
        else:
            log.warning("Failed to post: %s", it.get("url"))
    return sent
