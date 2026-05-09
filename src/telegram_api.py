"""Thin Telegram Bot API helpers (no library dependency)."""
import logging
import os

import requests

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"].strip()


def _call(method: str, **payload) -> dict | None:
    url = API_BASE.format(token=_token(), method=method)
    try:
        r = requests.post(url, json=payload, timeout=20)
        data = r.json()
        if not data.get("ok"):
            log.warning("Telegram %s failed: %s", method, data)
            return None
        return data.get("result")
    except Exception as e:
        log.exception("Telegram %s exception: %s", method, e)
        return None


def get_updates(offset: int, timeout: int = 0) -> list[dict]:
    res = _call("getUpdates", offset=offset, timeout=timeout,
                allowed_updates=["message", "callback_query"])
    return res or []


def send_message(chat_id, text: str, reply_markup=None,
                 reply_to_message_id: int | None = None,
                 disable_preview: bool = False) -> dict | None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {
            "is_disabled": disable_preview,
            "prefer_large_media": True,
        },
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id:
        payload["reply_parameters"] = {"message_id": reply_to_message_id,
                                        "allow_sending_without_reply": True}
    return _call("sendMessage", **payload)


def edit_message_text(chat_id, message_id: int, text: str,
                       reply_markup=None) -> bool:
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _call("editMessageText", **payload) is not None


def edit_message_reply_markup(chat_id, message_id: int, reply_markup=None) -> bool:
    payload = {"chat_id": chat_id, "message_id": message_id,
               "reply_markup": reply_markup or {"inline_keyboard": []}}
    return _call("editMessageReplyMarkup", **payload) is not None


def answer_callback_query(callback_query_id: str, text: str = "",
                           show_alert: bool = False) -> bool:
    return _call("answerCallbackQuery", callback_query_id=callback_query_id,
                  text=text, show_alert=show_alert) is not None
