"""Sends drafts to owner DM with inline keyboard for approval."""
import logging
import os

from . import pending, telegram_api

log = logging.getLogger(__name__)


def owner_chat_id(state: dict) -> int | None:
    explicit = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
    if explicit and explicit.lstrip("-").isdigit():
        return int(explicit)
    return state.get("owner_chat_id")


def _keyboard(pid: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Опубликовать", "callback_data": f"pub:{pid}"},
            {"text": "✏️ Изменить", "callback_data": f"edit:{pid}"},
            {"text": "❌ Пропустить", "callback_data": f"skip:{pid}"},
        ]]
    }


def send_for_approval(state: dict, post_text: str,
                       sources: list[dict] | None = None,
                       original_url: str = "",
                       kind: str = "digest") -> bool:
    chat_id = owner_chat_id(state)
    if not chat_id:
        log.warning("Owner chat_id unknown — cannot send draft. "
                    "Owner must /start the bot first.")
        return False

    pid = pending.add(state, post_text, sources or [], original_url, kind=kind)
    res = telegram_api.send_message(
        chat_id, post_text, reply_markup=_keyboard(pid), disable_preview=False,
    )
    if not res:
        pending.remove(state, pid)
        return False

    pending.update_message_id(state, pid, res["message_id"])
    log.info("Draft %s [%s] sent for approval (msg %s)", pid, kind, res["message_id"])
    return True


def send_items_for_approval(state: dict, items: list[dict],
                             kind: str = "digest") -> int:
    n = 0
    for it in items:
        post_text = it.get("post_text", "")
        if not post_text:
            continue
        sources = it.get("supporting_sources") or [
            {"name": it.get("source_name", ""), "url": it.get("url", "")}
        ]
        if send_for_approval(state, post_text, sources,
                              original_url=it.get("url", ""), kind=kind):
            n += 1
    log.info("Sent %d items for approval (kind=%s)", n, kind)
    return n
