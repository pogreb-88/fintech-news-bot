"""
Long-poll listener loop.

Sits in a `getUpdates(timeout=30)` loop, processing Telegram callbacks /
messages as they arrive. Designed to run inside a GitHub Actions workflow
that's started by cron every ~30 min. Each invocation runs up to
LISTENER_MAX_SECONDS (default ~25 min) and exits cleanly so the next cron
takes over.

Latency between user click and bot reaction: a few seconds (vs hours with
the old short-cron approval loop).
"""
import logging
import os
import time

from . import approver, state as state_mod, telegram_api

log = logging.getLogger(__name__)


def run_loop() -> None:
    max_seconds = int(os.environ.get("LISTENER_MAX_SECONDS", "1500"))  # 25 min
    long_poll = int(os.environ.get("LISTENER_POLL_TIMEOUT", "30"))     # 30 sec

    st = state_mod.load_state()
    start = time.monotonic()
    iterations = 0
    log.info(
        "listener starting: max=%ds, long_poll=%ds, pending=%d, offset=%s",
        max_seconds, long_poll, len(st.get("pending", [])),
        st.get("tg_update_offset", 0),
    )

    while time.monotonic() - start < max_seconds:
        iterations += 1
        offset = int(st.get("tg_update_offset", 0))
        try:
            updates = telegram_api.get_updates(offset, timeout=long_poll)
        except Exception as e:
            log.exception("get_updates error: %s", e)
            time.sleep(5)
            continue

        if updates:
            log.info("iter %d: %d update(s)", iterations, len(updates))
            try:
                approver.process_updates(st, updates)
                state_mod.save_state(st)
            except Exception as e:
                log.exception("process_updates error: %s", e)

    elapsed = time.monotonic() - start
    log.info(
        "listener exiting: ran %.1fs, %d iterations, pending=%d, offset=%s",
        elapsed, iterations, len(st.get("pending", [])),
        st.get("tg_update_offset", 0),
    )
    state_mod.save_state(st)
