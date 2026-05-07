"""Stage-2 writer: produces an editorial Russian Telegram post per selected item."""
import json
import logging
import os
import re

from anthropic import Anthropic

log = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

WRITER_PROMPT = """Ты пишешь короткий пост для Telegram-канала о high-risk fintech \
compliance (crypto/VASP, EMI/PSP, gambling, sanctions, AML). Аудитория — \
практикующие комплаенс-офицеры, юристы, владельцы fintech-бизнесов.

Голос: разговорно-экспертный. Прямое обращение к читателю допустимо \
("стоит обратить внимание", "учитывайте"). Никогда не используй первое лицо \
("я", "мы", "у меня", "по моему опыту") — пиши как наблюдатель.

Структура поста:
1. Первая строка — крючок: вопрос, резкое утверждение или яркий факт. \
Начинай с эмодзи-флага юрисдикции (🇬🇧 🇺🇸 🇪🇺 🇦🇪 🇸🇬 🇩🇪 🇫🇷 🇨🇾 🇲🇹 🇵🇱 🇵🇹 \
🇱🇹 🇮🇪 🇮🇹 🇳🇱 🇪🇸 🇨🇭 🇷🇺 🇨🇳 🇯🇵 🇧🇷 🇨🇦 🇦🇺 🇭🇰 🇿🇦 🌍).

2. 1-2 предложения — что произошло, простыми словами.

3. (Опционально) Жирный подзаголовок с эмодзи + список деталей через тире:
   ❗ <b>Что произошло:</b> для событий
   📌 <b>Что нашли:</b> или <b>Какие нарушения:</b> для enforcement
   ✅ <b>Что разрешено:</b> или <b>Что разъяснили:</b> для guidance
   ⚠️ <b>На что обратить внимание:</b> для рисков
   Каждый пункт начинается с — (длинное тире).

4. Закрывающий абзац (1-2 предложения) — что это значит для compliance-команд \
и бизнесов в high-risk сегменте. БЕЗ заголовка-плашки и БЕЗ слов \
"что важно", "вывод", "итог" в начале — просто естественный переход \
к импликациям. Только фактические следствия, без хайпа и без \
догадок о будущих событиях, не следующих из источника.

5. Ссылки на источники одной строкой в конце текста, встроенные в фразу: \
«Подробнее в <a href="URL1">материале REGULATOR</a> и <a href="URL2">репортаже OUTLET</a>.» \
1-2 ссылки максимум.

6. Хэштеги последней строкой: #категория #подкатегория + флаг юрисдикции.

ЖЁСТКИЕ ПРАВИЛА:
- Используй ТОЛЬКО факты из переданного материала. Никаких выдуманных цифр, \
дат, имён, цитат. Если входные данные куцые — пиши короче, не выдумывай.
- 120-250 слов. Жёсткий потолок 300.
- Только HTML-разметка для Telegram parse_mode=HTML: <b>, <a href="">, <i>. \
Никакого Markdown, никаких звёздочек, никаких [].
- Запрет на первое лицо.
- Никаких меток "✅ Подтверждено" / "⚠️ Не подтверждено".
- Не используй цветные точки 🔴🟠🟡 для важности.

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


def write_post(item: dict, article_body: str = "") -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)

    sources_lines = []
    for s in item.get("supporting_sources") or [
        {"name": item.get("source_name", ""), "url": item.get("url", "")}
    ]:
        sources_lines.append(f"- {s['name']}: {s['url']}")
    sources_block = "\n".join(sources_lines)

    user = (
        f"Заголовок (EN): {item.get('english_headline', item.get('title', ''))}\n"
        f"Категория: {item.get('category', 'other')}\n"
        f"Юрисдикция: {item.get('jurisdiction', 'GLOBAL')}\n"
        f"Важность (1-5): {item.get('importance', 0)}\n"
        f"Краткое содержание (RU): {item.get('russian_summary', '')}\n\n"
        f"Полный текст статьи (если доступен):\n"
        f"{article_body[:5000] if article_body else '(нет — используй только заголовок и summary выше)'}\n\n"
        f"Источники (выбери 1-2 для встраивания в текст):\n{sources_block}"
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=[{
                "type": "text",
                "text": WRITER_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user}],
        )
        data = _extract_json(resp.content[0].text)
        post = (data.get("post_text") or "").strip()
        return post or None
    except Exception as e:
        log.exception("Writer failed for %s: %s", item.get("url"), e)
        return None
