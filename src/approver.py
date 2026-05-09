"""Polls Telegram for callbacks (button clicks) and edit replies, publishes to channel."""
import logging
import os

from . import pending, poster, state as state_mod, telegram_api

log = logging.getLogger(__name__)


def _owner_chat_id(state: dict) -> int | None:
    explicit = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
    if explicit and explicit.lstrip("-").isdigit():
        return int(explicit)
    return state.get("owner_chat_id")


def _strip_keyboard(chat_id, message_id):
    telegram_api.edit_message_reply_markup(chat_id, message_id, None)


def _ack(cb_id, chat_id, fallback_text: str, toast: str | None = None) -> None:
    """Try answerCallbackQuery (toast). If it fails (e.g. >30s old query),
    send a regular DM message so the owner sees feedback anyway."""
    if toast is None:
        toast = fallback_text
    answered = telegram_api.answer_callback_query(cb_id, toast)
    if not answered:
        telegram_api.send_message(chat_id, fallback_text)


def _publish_and_record(state: dict, p: dict, post_text: str) -> bool:
    """Send to channel; on success, mark as posted in state."""
    if not poster.send_message(post_text):
        return False
    state_mod.mark_posted(state, {
        "url": p.get("original_url", ""),
        "english_headline": "",
        "category": p.get("kind", "other"),
        "russian_summary": "",
        "post_text": post_text,
    })
    return True


def poll(state: dict) -> None:
    offset = int(state.get("tg_update_offset", 0))
    log.info("poll start: offset=%d, pending_count=%d, owner_chat_id=%s",
             offset, len(state.get("pending", [])), state.get("owner_chat_id"))
    updates = telegram_api.get_updates(offset)
    log.info("got %d updates", len(updates))

    for u in updates:
        log.info("update %s: keys=%s", u.get("update_id"), list(u.keys()))
        offset = max(offset, u["update_id"] + 1)
        try:
            if "callback_query" in u:
                _handle_callback(state, u["callback_query"])
            elif "message" in u:
                _handle_message(state, u["message"])
        except Exception as e:
            log.exception("Update processing failed: %s", e)

    state["tg_update_offset"] = offset
    expired = pending.expire(state)
    if expired:
        log.info("Expired %d pending drafts past TTL", expired)
    log.info("poll end: new_offset=%d, pending_count=%d",
             offset, len(state.get("pending", [])))


def _handle_callback(state: dict, cb: dict) -> None:
    log.info("callback: data=%r id=%s has_message=%s",
             cb.get("data"), cb.get("id"), "message" in cb)
    data = cb.get("data", "")
    cb_id = cb["id"]
    if "message" not in cb:
        log.warning("callback has no message field, cannot answer with edit; "
                    "answering inline")
        telegram_api.answer_callback_query(cb_id, "Callback из устаревшего сообщения")
        return
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    original_text = cb["message"].get("text") or ""

    if ":" not in data:
        telegram_api.answer_callback_query(cb_id, "Неизвестная команда")
        return

    action, pid = data.split(":", 1)
    p = pending.find_by_id(state, pid)
    if not p:
        _ack(cb_id, chat_id, "Черновик уже обработан или истёк")
        _strip_keyboard(chat_id, msg_id)
        return

    if action == "pub":
        if _publish_and_record(state, p, p["post_text"]):
            telegram_api.edit_message_text(
                chat_id, msg_id, original_text + "\n\n— ✅ опубликовано —",
                reply_markup={"inline_keyboard": []},
            )
            _ack(cb_id, chat_id, "✅ Пост опубликован в канал")
            pending.remove(state, pid)
        else:
            _ack(cb_id, chat_id,
                 "❌ Ошибка отправки в канал — попробуй ещё раз клик.")

    elif action == "skip":
        telegram_api.edit_message_text(
            chat_id, msg_id, original_text + "\n\n— ❌ пропущено —",
            reply_markup={"inline_keyboard": []},
        )
        _ack(cb_id, chat_id, "❌ Черновик пропущен")
        pending.remove(state, pid)

    elif action == "edit":
        pending.set_status(state, pid, "awaiting_edit")
        _ack(cb_id, chat_id,
             "✏️ Пришли исправленную версию <b>ответом</b> (reply) на черновик выше.",
             toast="Жду исправленный текст")

    else:
        _ack(cb_id, chat_id, "Неизвестное действие")


def _handle_message(state: dict, msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    chat_id = msg["chat"]["id"]

    # /start: register chat_id
    if text.startswith("/start"):
        state["owner_chat_id"] = chat_id
        telegram_api.send_message(
            chat_id,
            "Привет! Этот бот будет присылать черновики постов сюда. "
            "Кнопками внизу каждого черновика — ✅ опубликовать / ✏️ изменить / "
            "❌ пропустить. Для редактирования: после ✏️ ответь reply'ем "
            "с правленым текстом.",
        )
        return

    # Edit reply
    reply_to = msg.get("reply_to_message")
    if not reply_to:
        return

    p = pending.find_by_message_id(state, reply_to["message_id"])
    if not p or p.get("status") != "awaiting_edit":
        return

    edited = msg.get("text", "")
    if not edited:
        return

    if _publish_and_record(state, p, edited):
        telegram_api.send_message(
            chat_id, "✅ Опубликована твоя версия",
            reply_to_message_id=msg["message_id"],
        )
        pending.remove(state, p["id"])
    else:
        telegram_api.send_message(
            chat_id, "Ошибка публикации в канал — проверь HTML-разметку и пришли ещё раз.",
            reply_to_message_id=msg["message_id"],
        )
