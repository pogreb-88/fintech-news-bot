"""
Entry point. Modes:

  python -m src.main digest    — slot-aware (morning/evening), drafts → owner DM
  python -m src.main breaking  — fetch last 90min, drafts → owner DM (importance>=4)
  python -m src.main weekly    — Monday-morning previous-week recap → owner DM
  python -m src.main approve   — poll for owner button clicks / edit replies
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from . import (
    approver, article, classifier, fetcher, listener, proposer, scheduler,
    state, verifier, weekly, writer,
)

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


def _check_owner_known(state_obj: dict) -> bool:
    chat_id = proposer.owner_chat_id(state_obj)
    if not chat_id:
        log.error(
            "Owner chat_id is unknown. Send /start to the bot in private DM, "
            "then the next 'approve' run will register it. Or set "
            "TELEGRAM_OWNER_CHAT_ID secret with a numeric chat_id."
        )
        return False
    return True


def _write_posts(verified_items: list[dict]) -> list[dict]:
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


def _run_pipeline(st: dict, max_age_hours: int, top_n: int | None,
                   min_importance: int = 0) -> list[dict]:
    raw = fetcher.fetch_all(max_age_hours=max_age_hours)
    raw = [it for it in raw if not state.is_seen(st, it["url"])]
    log.info("After dedup: %d new items", len(raw))
    if not raw:
        return []

    classified = classifier.classify(raw)
    if min_importance:
        classified = [it for it in classified
                      if int(it.get("importance", 0)) >= min_importance]
    if not classified:
        return []

    verified_items = verifier.verify(classified)
    if not verified_items:
        return []

    verified_items.sort(
        key=lambda it: (-int(it.get("importance", 0)), it.get("category", "")),
    )
    if top_n:
        verified_items = verified_items[:top_n]

    return _write_posts(verified_items)


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

    if not _check_owner_known(st):
        state.save_state(st)
        return

    written = _run_pipeline(st, max_age_hours=max_age_hours, top_n=top_n)
    proposer.send_items_for_approval(st, written, kind="digest")

    if slot:
        scheduler.mark_ran(st, slot)
    state.prune(st)
    state.save_state(st)


def run_breaking(max_age_hours: int = 2, min_importance: int = 4) -> None:
    st = state.load_state()
    if not _check_owner_known(st):
        state.save_state(st)
        return

    written = _run_pipeline(st, max_age_hours=max_age_hours,
                              top_n=None, min_importance=min_importance)
    proposer.send_items_for_approval(st, written, kind="breaking")

    state.prune(st)
    state.save_state(st)


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

    if not _check_owner_known(st):
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

    proposer.send_for_approval(st, text, sources=[], original_url="weekly", kind="weekly")
    scheduler.mark_ran(st, "weekly_monday")
    state.save_state(st)


def run_approve() -> None:
    """One-shot poll. Legacy; prefer 'listen' mode for live reactions."""
    st = state.load_state()
    approver.poll(st)
    state.prune(st)
    state.save_state(st)


def run_listen() -> None:
    """Long-poll loop. Processes callbacks instantly while running."""
    listener.run_loop()


def main() -> None:
    load_dotenv()
    _check_env()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["digest", "breaking", "weekly", "approve", "listen"],
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    auto_force = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    force = args.force or auto_force

    if args.mode == "digest":
        run_digest(force=force)
    elif args.mode == "breaking":
        run_breaking()
    elif args.mode == "weekly":
        run_weekly(force=force)
    elif args.mode == "approve":
        run_approve()
    elif args.mode == "listen":
        run_listen()


if __name__ == "__main__":
    main()
