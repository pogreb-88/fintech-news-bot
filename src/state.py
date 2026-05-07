"""State persistence. Stored in data/state.json, committed back by GH workflow."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / "data" / "state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"posted": [], "weekly_buffer": []}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def is_seen(state: dict, url: str) -> bool:
    h = url_hash(url)
    return any(p["hash"] == h for p in state["posted"])


def mark_posted(state: dict, item: dict) -> None:
    """item is a classified+verified news item."""
    state["posted"].append({
        "hash": url_hash(item["url"]),
        "url": item["url"],
        "headline": item.get("english_headline", item.get("title", "")),
        "category": item.get("category", "other"),
        "importance": item.get("importance", 0),
        "verified": item.get("verified", False),
        "posted_at": _now_iso(),
    })
    state["weekly_buffer"].append({
        "url": item["url"],
        "headline": item.get("english_headline", item.get("title", "")),
        "summary": item.get("russian_summary", ""),
        "category": item.get("category", "other"),
        "importance": item.get("importance", 0),
        "verified": item.get("verified", False),
        "posted_at": _now_iso(),
    })


def prune(state: dict, keep_days: int = 60) -> None:
    """Drop posted items older than keep_days; weekly_buffer older than 8 days."""
    cutoff_post = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_week = datetime.now(timezone.utc) - timedelta(days=8)

    def _parse(s: str) -> datetime:
        return datetime.fromisoformat(s)

    state["posted"] = [p for p in state["posted"] if _parse(p["posted_at"]) > cutoff_post]
    state["weekly_buffer"] = [
        p for p in state["weekly_buffer"] if _parse(p["posted_at"]) > cutoff_week
    ]


def consume_weekly_buffer(state: dict) -> list[dict]:
    """Return weekly buffer and clear it (caller saves state after posting)."""
    items = list(state["weekly_buffer"])
    state["weekly_buffer"] = []
    return items
