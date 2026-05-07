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
        return _blank()
    with open(STATE_FILE, encoding="utf-8") as f:
        st = json.load(f)
    # Backfill missing keys (forward-compat with older state files)
    blank = _blank()
    for k, v in blank.items():
        st.setdefault(k, v)
    return st


def _blank() -> dict:
    return {
        "posted": [],
        "weekly_buffer": [],
        "last_digest_morning": "",   # YYYY-MM-DD of last morning run (Prague date)
        "last_digest_evening": "",   # YYYY-MM-DD of last evening run
        "last_weekly": "",           # ISO week id like 2026-W19
    }


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
    state["posted"].append({
        "hash": url_hash(item["url"]),
        "url": item["url"],
        "headline": item.get("english_headline", item.get("title", "")),
        "category": item.get("category", "other"),
        "jurisdiction": item.get("jurisdiction", "GLOBAL"),
        "importance": item.get("importance", 0),
        "posted_at": _now_iso(),
    })
    state["weekly_buffer"].append({
        "url": item["url"],
        "headline": item.get("english_headline", item.get("title", "")),
        "summary": item.get("russian_summary", ""),
        "post_text": item.get("post_text", ""),
        "category": item.get("category", "other"),
        "jurisdiction": item.get("jurisdiction", "GLOBAL"),
        "importance": item.get("importance", 0),
        "posted_at": _now_iso(),
    })


def prune(state: dict, keep_days: int = 60) -> None:
    cutoff_post = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_week = datetime.now(timezone.utc) - timedelta(days=14)

    def _parse(s: str) -> datetime:
        return datetime.fromisoformat(s)

    state["posted"] = [p for p in state["posted"] if _parse(p["posted_at"]) > cutoff_post]
    state["weekly_buffer"] = [
        p for p in state["weekly_buffer"] if _parse(p["posted_at"]) > cutoff_week
    ]


def previous_week_items(state: dict) -> list[dict]:
    """Items posted during the previous calendar week (Mon 00:00 — Sun 23:59 UTC)."""
    now = datetime.now(timezone.utc)
    today = now.date()
    # Monday of this week
    this_week_mon = today - timedelta(days=today.weekday())
    last_week_mon = this_week_mon - timedelta(days=7)
    last_week_sun_end = this_week_mon  # exclusive upper bound

    def _in_window(s: str) -> bool:
        d = datetime.fromisoformat(s).date()
        return last_week_mon <= d < last_week_sun_end

    return [p for p in state["weekly_buffer"] if _in_window(p["posted_at"])]
