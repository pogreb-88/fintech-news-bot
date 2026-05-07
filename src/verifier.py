"""
Cluster items by underlying event, drop unverifiable single-source non-regulator items.

After verify():
- Each remaining item has supporting_sources (1-N)
- Items where the only source is press AND there's no corroboration are dropped
  (single-source unverified content not posted, per channel policy)
- Regulator-only single sources are kept (regulator is authoritative)
"""
import json
import logging
import os
import re

from anthropic import Anthropic

log = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

CLUSTER_PROMPT = """You will be given a list of news items, each with id, headline, \
and source. Group items that describe the SAME underlying real-world event \
(same incident, same announcement, same regulatory action, same fine).

Generic topical similarity is NOT enough.

Return JSON array of clusters: [{"event": "<short label>", "ids": [<id>, ...]}].
Every input id must appear in exactly one cluster (singletons allowed).
Return JSON only."""


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1:
        raise ValueError(f"No JSON array in: {text[:200]}")
    return json.loads(text[start : end + 1])


def _cluster(items: list[dict]) -> list[list[int]]:
    if len(items) <= 1:
        return [[i] for i in range(len(items))]

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    client = Anthropic(api_key=api_key)
    payload = [
        {"id": i, "headline": it["english_headline"], "source": it["source_name"]}
        for i, it in enumerate(items)
    ]

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=CLUSTER_PROMPT,
            messages=[{
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            }],
        )
        clusters = _extract_json(resp.content[0].text)
        result = []
        seen: set[int] = set()
        for c in clusters:
            ids = [int(x) for x in c.get("ids", []) if isinstance(x, (int, str))]
            ids = [i for i in ids if 0 <= i < len(items) and i not in seen]
            if ids:
                result.append(ids)
                seen.update(ids)
        for i in range(len(items)):
            if i not in seen:
                result.append([i])
        return result
    except Exception as e:
        log.exception("Cluster failed, falling back to singletons: %s", e)
        return [[i] for i in range(len(items))]


def verify(items: list[dict]) -> list[dict]:
    """Returns items that pass the source-quality bar. Drops unverifiable singletons."""
    if not items:
        return []

    clusters = _cluster(items)
    out: list[dict] = []
    dropped = 0

    for cluster_ids in clusters:
        cluster = [items[i] for i in cluster_ids]
        domains = {it["source_domain"] for it in cluster}
        has_regulator = any(it["source_type"] == "regulator" for it in cluster)
        independent_count = len(domains)

        # Drop policy: single-source AND non-regulator => not posted
        if independent_count < 2 and not has_regulator:
            dropped += 1
            continue

        cluster.sort(
            key=lambda it: (
                0 if it["source_type"] == "regulator" else 1,
                -int(it.get("importance", 0)),
                it["url"],
            )
        )
        rep = dict(cluster[0])
        rep["supporting_sources"] = [
            {"name": it["source_name"], "url": it["url"], "type": it["source_type"]}
            for it in cluster
        ]
        out.append(rep)

    log.info("Verified: %d clusters kept, %d dropped (single-source unverified)",
             len(out), dropped)
    return out
