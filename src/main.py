"""
Entry point. Three modes:

  python -m src.main digest    — fetch last 12h, classify, verify, post top items
  python -m src.main breaking  — fetch last 90min, post only importance>=4
  python -m src.main weekly    — produce weekly digest from buffer
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from . import classifier, fetcher, poster, state, verifier, weekly

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("main")


def _check_env() -> None:
    """Validate and trim required env vars (whitespace from Secrets paste is a real issue)."""
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "ANTHROPIC_API_KEY"):
        raw = os.environ.get(k, "")
        trimmed = raw.strip()
        if not trimmed:
            sys.exit(f"Missing env var: {k}")
        if trimmed != raw:
            log.warning("%s had surrounding whitespace, trimmed", k)
            os.environ[k] = trimmed


def run_digest(max_age_hours: int = 12, top_n: int = 7) -> None:
    st = state.load_state()
    raw = fetcher.fetch_all(max_age_hours=max_age_hours)
    raw = [it for it in raw if not state.is_seen(st, it["url"])]
    log.info("After dedup: %d new items", len(raw))
    if not raw:
        return

    classified = classifier.classify(raw)
    if not classified:
        return

    verified_items = verifier.verify(classified)
    verified_items.sort(
        key=lambda it: (-int(it.get("importance", 0)), it.get("category", "")),
    )
    selected = verified_items[:top_n]

    sent = poster.post_items(selected)
    for it in sent:
        state.mark_posted(st, it)
    state.prune(st)
    state.save_state(st)
    log.info("Digest: posted %d items", len(sent))


def run_breaking(max_age_hours: int = 2, min_importance: int = 4) -> None:
    st = state.load_state()
    raw = fetcher.fetch_all(max_age_hours=max_age_hours)
    raw = [it for it in raw if not state.is_seen(st, it["url"])]
    if not raw:
        return

    classified = classifier.classify(raw)
    classified = [
        it for it in classified if int(it.get("importance", 0)) >= min_importance
    ]
    if not classified:
        return

    verified_items = verifier.verify(classified)

    sent = poster.post_items(verified_items)
    for it in sent:
        state.mark_posted(st, it)
    state.prune(st)
    state.save_state(st)
    log.info("Breaking: posted %d items", len(sent))


def run_weekly() -> None:
    st = state.load_state()
    items = state.consume_weekly_buffer(st)
    if not items:
        log.info("Weekly: no items in buffer, skipping")
        state.save_state(st)
        return

    text = weekly.generate_digest(items)
    if not text:
        log.warning("Weekly: digest generation returned nothing")
        return

    header = "📊 <b>Сводка недели — high-risk fintech</b>\n\n"
    if poster.send_message(header + text):
        log.info("Weekly digest posted (%d items consumed)", len(items))
        state.save_state(st)


def main() -> None:
    load_dotenv()
    _check_env()

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["digest", "breaking", "weekly"])
    args = parser.parse_args()

    if args.mode == "digest":
        run_digest()
    elif args.mode == "breaking":
        run_breaking()
    elif args.mode == "weekly":
        run_weekly()


if __name__ == "__main__":
    main()
