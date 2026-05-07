"""Stage-1 filter: cheap relevance + category + importance + jurisdiction."""
import json
import logging
import os
import re
from html import unescape

from anthropic import Anthropic

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_BATCH = 12

CATEGORIES = [
    "crypto", "payments", "gambling", "adult_psp",
    "sanctions", "aml", "regulator_action", "other",
]

JURISDICTIONS = [
    "UK", "US", "EU", "AE", "SG", "DE", "FR", "CY", "MT", "PL", "PT",
    "LT", "IE", "IT", "NL", "ES", "CH", "RU", "CN", "JP", "BR", "CA",
    "AU", "HK", "ZA", "GLOBAL",
]

SYSTEM_PROMPT = f"""You filter financial news for a high-risk fintech compliance \
audience. Topics of interest:
- crypto / VASP / CASP / stablecoins
- EMI / PSP / PI / MSB / money transmitters / BaaS
- gambling / iGaming
- payment processors serving high-risk merchants (adult, nutra, gambling)
- sanctions (OFAC, EU, UK, UN)
- AML/CTF enforcement, fines, programme deficiencies
- regulator actions (licence revocations, grants, supervisory orders)

For each item return JSON with:
- id (echo input id)
- relevant (bool): true ONLY if directly concerns the topics above
- category (one of: {', '.join(CATEGORIES)})
- importance (1-5): 5 = major regulator action, large fine, sanctions package, \
licence revocation; 4 = significant policy change or major company event; \
3 = notable enforcement or filing; 2 = routine but useful; 1 = peripheral
- jurisdiction (one of: {', '.join(JURISDICTIONS)}): primary jurisdiction the \
story concerns. Use GLOBAL for cross-border / multi-jurisdictional / FATF / \
international standards.
- english_headline (concise English, <= 90 chars)
- russian_summary (2-3 sentences in clear Russian, factual, no fluff)

Return a JSON array only — no prose."""


def _clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in: {text[:200]}")
    return json.loads(text[start : end + 1])


def classify(items: list[dict]) -> list[dict]:
    if not items:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)

    annotated: list[dict] = []
    for batch_start in range(0, len(items), MAX_BATCH):
        batch = items[batch_start : batch_start + MAX_BATCH]
        payload = [
            {
                "id": batch_start + i,
                "title": it["title"],
                "summary": _clean_html(it["summary"])[:600],
                "source": it["source_name"],
            }
            for i, it in enumerate(batch)
        ]

        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{
                    "role": "user",
                    "content": "Items:\n" + json.dumps(payload, ensure_ascii=False),
                }],
            )
            results = _extract_json(resp.content[0].text)
        except Exception as e:
            log.exception("Classify batch failed: %s", e)
            continue

        by_id = {r["id"]: r for r in results if isinstance(r, dict) and "id" in r}
        for i, it in enumerate(batch):
            r = by_id.get(batch_start + i)
            if not r or not r.get("relevant"):
                continue
            jur = r.get("jurisdiction", "GLOBAL")
            if jur not in JURISDICTIONS:
                jur = "GLOBAL"
            annotated.append({
                **it,
                "category": r.get("category", "other"),
                "importance": int(r.get("importance", 0)),
                "jurisdiction": jur,
                "russian_summary": r.get("russian_summary", "").strip(),
                "english_headline": r.get("english_headline", it["title"]).strip(),
            })

    log.info("Classified %d items, %d relevant", len(items), len(annotated))
    return annotated
