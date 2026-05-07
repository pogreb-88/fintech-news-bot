"""Weekly digest writer — single Telegram post recapping the previous calendar week."""
import json
import logging
import os
import re

from anthropic import Anthropic

log = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

DIGEST_PROMPT = """Ты пишешь воскресный (точнее — понедельничный утренний) дайджест \
прошлой недели для Telegram-канала о high-risk fintech compliance. Аудитория — \
комплаенс-практики и владельцы fintech-бизнесов.

Голос: разговорно-экспертный, без первого лица. Прямое обращение к читателю \
допустимо.

Структура поста:
1. Открытие: одно предложение про доминирующую тему недели или общее наблюдение.
2. <b>📌 Главное за неделю:</b> — топ-3-5 событий списком через тире, каждое: \
короткий заголовок + 1-2 предложения о сути и значении.
3. <b>⚠️ На что смотреть дальше:</b> — 1-2 предложения о том, что следить на \
этой неделе, ТОЛЬКО если это вытекает из материалов недели. Никаких прогнозов \
от себя.
4. Хэштеги последней строкой: #weeklydigest + 1-2 главные категории недели.

ЖЁСТКИЕ ПРАВИЛА:
- Только факты из переданных за неделю постов. Без выдуманных событий.
- 200-400 слов, потолок 500.
- HTML для Telegram parse_mode=HTML: <b>, <a href="">, <i>. Без Markdown.
- Запрет на первое лицо.
- Если событий за неделю было меньше 3 — пиши короче, не натягивай.

Верни JSON: { "post_text": "<готовый HTML-форматированный пост>" }"""


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1:
        raise ValueError(f"No JSON object in: {text[:200]}")
    return json.loads(text[start : end + 1])


def generate_digest(items: list[dict]) -> str | None:
    if not items:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    client = Anthropic(api_key=api_key)
    payload = [
        {
            "headline": it["headline"],
            "category": it["category"],
            "jurisdiction": it.get("jurisdiction", "GLOBAL"),
            "importance": it["importance"],
            "summary": it["summary"],
            "url": it["url"],
        }
        for it in items
    ]

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=[{
                "type": "text",
                "text": DIGEST_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": "Posts from the previous week:\n"
                            + json.dumps(payload, ensure_ascii=False, indent=2),
            }],
        )
        data = _extract_json(resp.content[0].text)
        return (data.get("post_text") or "").strip() or None
    except Exception as e:
        log.exception("Weekly digest generation failed: %s", e)
        return None
