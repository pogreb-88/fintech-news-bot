"""
Cross-source verification.

Strategy: ask Claude to cluster items by underlying real-world event,
then per cluster:
  - count distinct source_domains
  - regulator domain counts as authoritative (auto-verified if regulator + any press)
  - 2+ independent press domains also = verified
  - otherwise = unverified (⚠️)
"""
import json
import logging
import os
import re

from anthropic import Anthropic

log = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"

CLUSTER_PROMPT = """You will be given a list of news items, each with an id, headline, \
and source. Group items that describe the SAME underlying real-world event.

Two items belong to the same cluster ONLY if they refer to the same incident, \
the same announcement, the same regulatory action, the same fine, etc. \
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

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
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
        # ensure every item is somewhere
        for i in range(len(items)):
            if i not in seen:
                result.append([i])
        return result
    except Exception as e:
        log.exception("Cluster failed, falling back to singletons: %s", e)
        return [[i] for i in range(len(items))]


def verify(items: list[dict]) -> list[dict]:
    """
    For each item set: verified (bool), supporting_sources (list of source names).
    Picks one representative per cluster (highest importance, prefer regulator).
    """
    if not items:
        return []

    clusters = _cluster(items)
    out: list[dict] = []

    for cluster_ids in clusters:
        cluster = [items[i] for i in cluster_ids]
        domains = {it["source_domain"] for it in cluster}
        has_regulator = any(it["source_type"] == "regulator" for it in cluster)
        independent_count = len(domains)

        verified = (has_regulator and independent_count >= 2) or independent_count >= 2

        # Pick representative: regulator first, then highest importance
        cluster.sort(
            key=lambda it: (
                0 if it["source_type"] == "regulator" else 1,
                -int(it.get("importance", 0)),
                it["url"],
            )
        )
        rep = dict(cluster[0])
        rep["verified"] = verified
        rep["supporting_sources"] = [
            {"name": it["source_name"], "url": it["url"]} for it in cluster
        ]
        out.append(rep)

    log.info("Verified: %d clusters from %d items", len(out), len(items))
    return out
