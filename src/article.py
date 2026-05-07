"""Best-effort full article body fetcher.

Fetches the URL, extracts main text via BeautifulSoup, returns plain text.
Returns "" on failure (paywall, JS-only, network) — caller falls back to RSS summary.
"""
import logging
import re

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

MAX_CHARS = 6000


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]


def fetch(url: str, timeout: int = 8) -> str:
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        if r.status_code != 200 or not r.text:
            return ""

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                          "form", "iframe", "noscript", "button"]):
            tag.decompose()

        # Try semantic containers first
        for selector in ["article", "main", '[role="main"]', ".article-body",
                          ".story-body", ".post-content", "#content", "#main"]:
            el = soup.select_one(selector)
            if el:
                text = _clean(el.get_text(separator=" "))
                if len(text) > 250:
                    return text

        # Fallback: concatenate all <p>
        ps = soup.find_all("p")
        text = _clean(" ".join(p.get_text(separator=" ", strip=True) for p in ps))
        return text if len(text) > 250 else ""
    except Exception as e:
        log.warning("Article fetch failed for %s: %s", url, e)
        return ""
