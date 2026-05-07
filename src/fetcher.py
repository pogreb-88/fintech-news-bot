"""Fetch RSS feeds and normalize into a unified item shape."""
import logging
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from .sources import SOURCES, domain_of

log = logging.getLogger(__name__)


def _parse_date(entry) -> datetime | None:
    for key in ("published", "updated", "created"):
        v = entry.get(key)
        if not v:
            continue
        try:
            return parsedate_to_datetime(v).astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def fetch_all(max_age_hours: int = 24) -> list[dict]:
    """
    Fetch every source. Return items younger than max_age_hours.

    Each item: {url, title, summary, source_name, source_type, source_domain,
                published_at (iso), weight}.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items: list[dict] = []

    for src in SOURCES:
        try:
            log.info("Fetching %s", src["name"])
            feed = feedparser.parse(src["url"], request_headers={
                "User-Agent": "fintech-news-bot/1.0",
            })
            if feed.bozo and not feed.entries:
                log.warning("Failed to parse %s: %s", src["name"], feed.bozo_exception)
                continue

            for entry in feed.entries:
                url = entry.get("link")
                if not url:
                    continue

                pub = _parse_date(entry)
                if pub is None:
                    pub = datetime.now(timezone.utc)
                if pub < cutoff:
                    continue

                items.append({
                    "url": url,
                    "title": (entry.get("title") or "").strip(),
                    "summary": (entry.get("summary") or entry.get("description") or "").strip(),
                    "source_name": src["name"],
                    "source_type": src["type"],
                    "source_domain": domain_of(src["name"], src["url"]),
                    "published_at": pub.isoformat(),
                    "weight": src["weight"],
                })
        except Exception as e:
            log.exception("Error fetching %s: %s", src["name"], e)
        finally:
            time.sleep(0.4)

    log.info("Fetched %d items in last %dh", len(items), max_age_hours)
    return items
