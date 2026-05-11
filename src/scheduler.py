"""
Slot-based scheduling.

GitHub Actions scheduled workflows are unreliable — cron triggers can be
delayed 1-3 hours during high-load periods. We compensate by:
1. Multiple cron triggers per slot (more shots on goal).
2. Wide slot windows (any fire within the window triggers a run).
3. Once-per-day dedup via state.last_digest_{morning,evening}.

Slot windows (UTC) — chosen so Prague-time daylight hours are covered:
  morning : 06:00 - 13:00 UTC   (08:00-15:00 Prague summer)
  evening : 14:00 - 21:00 UTC   (16:00-23:00 Prague summer)
  weekly  : Monday 06:00 - 13:00 UTC
"""
from datetime import date, datetime, timezone


def _today() -> date:
    return date.today()


def _iso_week_id(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def determine_digest_slot(now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    h = now.hour
    if 6 <= h < 13:
        return "morning"
    if 14 <= h < 21:
        return "evening"
    return None


def in_active_slot(slot: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if slot == "weekly_monday":
        return now.weekday() == 0 and 6 <= now.hour < 13
    return determine_digest_slot(now) == slot


def already_ran_today(state: dict, slot: str) -> bool:
    if slot == "weekly_monday":
        return state.get("last_weekly", "") == _iso_week_id(_today())
    key = "last_digest_" + slot
    return state.get(key, "") == _today().isoformat()


def mark_ran(state: dict, slot: str) -> None:
    if slot == "weekly_monday":
        state["last_weekly"] = _iso_week_id(_today())
    else:
        state["last_digest_" + slot] = _today().isoformat()
