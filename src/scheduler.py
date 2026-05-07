"""
Slot-based randomized scheduling.

GitHub cron has no timezone support and no native randomness. Approach:
1. Workflow fires multiple times within a UTC window (e.g. every 30 min for 2h).
2. Each fire, we ask: is it time to run today's slot?
   - target_offset = deterministic random in [0, window_minutes], seeded by date+slot
   - run if (now >= window_start + target_offset) AND (today not yet run for this slot)

This produces ≤1 run per slot per day, at a different time each day.
"""
import random
from datetime import date, datetime, time, timedelta, timezone

# All windows in UTC. Adjust here if you want to anchor differently.
SLOTS = {
    "morning": {
        "window_start": time(7, 0),     # 09:00 Prague summer / 08:00 winter
        "window_minutes": 120,
        "state_key": "last_digest_morning",
    },
    "evening": {
        "window_start": time(15, 0),    # 17:00 Prague summer / 16:00 winter
        "window_minutes": 120,
        "state_key": "last_digest_evening",
    },
    "weekly_monday": {
        "window_start": time(7, 0),     # Monday 09:00 Prague summer
        "window_minutes": 120,
        "state_key": "last_weekly",
        "weekday": 0,                    # Monday only
    },
}


def _today_seed(slot: str) -> int:
    return int(date.today().isoformat().replace("-", "")) * 100 + hash(slot) % 100


def _target_offset_minutes(slot: str, window_minutes: int) -> int:
    rng = random.Random(_today_seed(slot))
    return rng.randint(0, window_minutes)


def in_active_slot(slot: str, now: datetime | None = None) -> bool:
    """Return True if it's time to run this slot (window passed target offset)."""
    cfg = SLOTS[slot]
    now = now or datetime.now(timezone.utc)

    # Weekly: only on configured weekday
    weekday = cfg.get("weekday")
    if weekday is not None and now.weekday() != weekday:
        return False

    window_start = datetime.combine(now.date(), cfg["window_start"], tzinfo=timezone.utc)
    target = window_start + timedelta(minutes=_target_offset_minutes(slot, cfg["window_minutes"]))
    window_end = window_start + timedelta(minutes=cfg["window_minutes"] + 30)

    return target <= now <= window_end


def already_ran_today(state: dict, slot: str) -> bool:
    cfg = SLOTS[slot]
    last = state.get(cfg["state_key"], "")
    if slot == "weekly_monday":
        # Mark by ISO week
        return last == _iso_week_id(date.today())
    return last == date.today().isoformat()


def mark_ran(state: dict, slot: str) -> None:
    cfg = SLOTS[slot]
    if slot == "weekly_monday":
        state[cfg["state_key"]] = _iso_week_id(date.today())
    else:
        state[cfg["state_key"]] = date.today().isoformat()


def _iso_week_id(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def determine_digest_slot(now: datetime | None = None) -> str | None:
    """Return 'morning' or 'evening' if currently active, else None."""
    now = now or datetime.now(timezone.utc)
    if in_active_slot("morning", now):
        return "morning"
    if in_active_slot("evening", now):
        return "evening"
    return None
