"""Weekly digest generation."""
import json
import logging
import os
import re

from anthropic import Anthropic

log = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

DIGEST_PROMPT = """You will be given a list of news items posted to a high-risk fintech \
compliance Telegram channel over the past week. Each item has a headline, category, \
importance, Russian summary, and verified flag.

Write a weekly digest in Russian:
1. One opening paragraph (2-3 sentences) — what was the dominant theme this week?
2. Top 5 stories — for each: one short paragraph in Russian (1-2 sentences) \
explaining the story AND its significance ("что это значит"). Pick stories with \
highest importance and broadest implications, not just chronologically latest.
3. One closing paragraph (1-2 sentences) — what to watch next week.

Plain prose, no bullets unless natural, no emojis. Concise, professional Russian."""


def generate_digest(items: list[dict]) -> str | None:
    if not items:
        return None

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    payload = [
        {
            "headline": it["headline"],
            "category": it["category"],
            "importance": it["importance"],
            "summary": it["summary"],
            "verified": it["verified"],
        }
        for it in items
    ]

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=DIGEST_PROMPT,
            messages=[{
                "role": "user",
                "content": "Items from this week:\n"
                            + json.dumps(payload, ensure_ascii=False, indent=2),
            }],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        log.exception("Digest generation failed: %s", e)
        return None
