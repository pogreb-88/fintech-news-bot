"""Pending-drafts queue. Items live until approved/edited/skipped or TTL expires."""
import uuid
from datetime import datetime, timedelta, timezone

DEFAULT_TTL_HOURS = 12


def _now() -> datetime:
    return datetime.now(timezone.utc)


def add(state: dict, post_text: str, sources: list[dict],
        original_url: str = "", kind: str = "digest",
        ttl_hours: int = DEFAULT_TTL_HOURS) -> str:
    pid = uuid.uuid4().hex[:8]
    state["pending"].append({
        "id": pid,
        "kind": kind,           # digest | breaking | weekly
        "post_text": post_text,
        "sources": sources,
        "original_url": original_url,
        "tg_message_id": None,
        "status": "draft",      # draft | sent | awaiting_edit
        "created_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(hours=ttl_hours)).isoformat(),
    })
    return pid


def find_by_id(state: dict, pid: str) -> dict | None:
    for p in state["pending"]:
        if p["id"] == pid:
            return p
    return None


def find_by_message_id(state: dict, message_id: int) -> dict | None:
    for p in state["pending"]:
        if p.get("tg_message_id") == message_id:
            return p
    return None


def find_awaiting_edit(state: dict) -> dict | None:
    """Most recent draft in awaiting_edit status (for non-reply edits)."""
    candidates = [p for p in state["pending"] if p.get("status") == "awaiting_edit"]
    return candidates[-1] if candidates else None


def remove(state: dict, pid: str) -> None:
    state["pending"] = [p for p in state["pending"] if p["id"] != pid]


def update_message_id(state: dict, pid: str, message_id: int) -> None:
    p = find_by_id(state, pid)
    if p:
        p["tg_message_id"] = message_id
        p["status"] = "sent"


def set_status(state: dict, pid: str, status: str) -> None:
    p = find_by_id(state, pid)
    if p:
        p["status"] = status


def expire(state: dict) -> int:
    now = _now()
    fresh, expired = [], 0
    for p in state["pending"]:
        if datetime.fromisoformat(p["expires_at"]) > now:
            fresh.append(p)
        else:
            expired += 1
    state["pending"] = fresh
    return expired
