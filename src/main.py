"""
Entry point. Three modes:

  python -m src.main digest    — slot-aware (morning/evening), random target time
  python -m src.main breaking  — fetch last 90min, post only importance>=4
  python -m src.main weekly    — Monday-morning previous-week recap
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from . import article, classifier, fetcher, poster, scheduler, state, verifier, weekly, writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("main")


def _check_env() -> None:
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "ANTHROPIC_API_KEY"):
        raw = os.environ.get(k, "")
        trimmed = raw.strip()
        if not trimmed:
            sys.exit(f"Missing env var: {k}")
        if trimmed != raw:
            log.warning("%s had surrounding whitespace, trimmed", k)
            os.environ[k] = trimmed


def _write_posts(verified_items: list[dict]) -> list[dict]:
    """Stage 2: fetch article body + run writer for each item."""
    out: list[dict] = []
    for it in verified_items:
        body = article.fetch(it["url"])
        log.info("Article body for %s: %d chars", it["url"], len(body))
        post_text = writer.write_post(it, article_body=body)
        if not post_text:
            log.warning("Writer returned empty for %s, skipping", it["url"])
            continue
        out.append({**it, "post_text": post_text})
    return out


def run_digest(force: bool = False, max_age_hours: int = 12, top_n: int = 5) -> None:
    st = state.load_state()

    if not force:
        slot = scheduler.determine_digest_slot()
        if not slot:
            log.info("Not in any digest slot window — exiting")
            state.save_state(st)
            return
        if scheduler.already_ran_today(st, slot):
            log.info("Slot '%s' already ran today — exiting", slot)
            state.save_state(st)
            return
        log.info("Active slot: %s", slot)
    else:
        slot = None
        log.info("Forced run (workflow_dispatch or local) — bypassing slot logic")

    raw = fetcher.fetch_all(max_age_hours=max_age_hours)
    raw = [it for it in raw if not state.is_seen(st, it["url"])]
    log.info("After dedup: %d new items", len(raw))
    if not raw:
        if slot:
            scheduler.mark_ran(st, slot)
        state.save_state(st)
        return

    classified = classifier.classify(raw)
    if not classified:
        if slot:
            scheduler.mark_ran(st, slot)
        state.save_state(st)
        return

    verified_items = verifier.verify(classified)
    if not verified_items:
        if slot:
            scheduler.mark_ran(st, slot)
        state.save_state(st)
        return

    verified_items.sort(
        key=lambda it: (-int(it.get("importance", 0)), it.get("category", "")),
    )
    selected = verified_items[:top_n]

    written = _write_posts(selected)
    sent = poster.post_items(written)
    for it in sent:
        state.mark_posted(st, it)
    if slot:
        scheduler.mark_ran(st, slot)
    state.prune(st)
    state.save_state(st)
    log.info("Digest: posted %d items", len(sent))


def run_breaking(max_age_hours: int = 2, min_importance: int = 4) -> None:
    st = state.load_state()
    raw = fetcher.fetch_all(max_age_hours=max_age_hours)
    raw = [it for it in raw if not state.is_seen(st, it["url"])]
    if not raw:
        state.save_state(st)
        return

    classified = classifier.classify(raw)
    classified = [it for it in classified if int(it.get("importance", 0)) >= min_importance]
    if not classified:
        state.save_state(st)
        return

    verified_items = verifier.verify(classified)
    if not verified_items:
        state.save_state(st)
        return

    written = _write_posts(verified_items)
    sent = poster.post_items(written)
    for it in sent:
        state.mark_posted(st, it)
    state.prune(st)
    state.save_state(st)
    log.info("Breaking: posted %d items", len(sent))


def run_weekly(force: bool = False) -> None:
    st = state.load_state()

    if not force:
        if not scheduler.in_active_slot("weekly_monday"):
            log.info("Not in weekly slot window — exiting")
            state.save_state(st)
            return
        if scheduler.already_ran_today(st, "weekly_monday"):
            log.info("Weekly already ran for this week — exiting")
            state.save_state(st)
            return

    items = state.previous_week_items(st)
    if not items:
        log.info("Weekly: no items for previous week, skipping")
        scheduler.mark_ran(st, "weekly_monday")
        state.save_state(st)
        return

    text = weekly.generate_digest(items)
    if not text:
        log.warning("Weekly: digest generation returned nothing")
        state.save_state(st)
        return

    if poster.send_message(text):
        log.info("Weekly digest posted (%d items recapped)", len(items))
    scheduler.mark_ran(st, "weekly_monday")
    state.save_state(st)


def main() -> None:
    load_dotenv()
    _check_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["digest", "breaking", "weekly"])
    parser.add_argument("--force", action="store_true",
                        help="Bypass slot timing checks (for manual runs)")
    args = parser.parse_args()

    # workflow_dispatch sets GITHUB_EVENT_NAME=workflow_dispatch — auto-force in that case
    auto_force = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    force = args.force or auto_force

    if args.mode == "digest":
        run_digest(force=force)
    elif args.mode == "breaking":
        run_breaking()
    elif args.mode == "weekly":
        run_weekly(force=force)


if __name__ == "__main__":
    main()
