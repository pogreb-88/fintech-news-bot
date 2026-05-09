"""
News sources. Each entry: {name, url, type, weight}.

type:
  - "regulator"  — primary, authoritative (counts as independent source)
  - "press"      — secondary reporting
  - "industry"   — niche industry coverage

weight: 1-3, used to prioritize when there are many items.
"""

SOURCES = [
    # === Regulators (primary) ===
    {
        "name": "FCA (UK)",
        "url": "https://www.fca.org.uk/news/rss.xml",
        "type": "regulator",
        "weight": 3,
    },
    {
        "name": "SEC (US)",
        "url": "https://www.sec.gov/news/pressreleases.rss",
        "type": "regulator",
        "weight": 3,
    },
    {
        "name": "FinCEN (US)",
        "url": "https://www.fincen.gov/news/news-releases/feed",
        "type": "regulator",
        "weight": 3,
    },
    {
        "name": "BaFin (DE)",
        "url": "https://www.bafin.de/SiteGlobals/Functions/RSSFeed/EN/RSSNewsfeed/RSSNewsfeed_EN.xml",
        "type": "regulator",
        "weight": 2,
    },
    {
        "name": "ESMA (EU)",
        "url": "https://www.esma.europa.eu/rss.xml",
        "type": "regulator",
        "weight": 2,
    },
    {
        "name": "EBA (EU)",
        "url": "https://www.eba.europa.eu/news-press/news/rss",
        "type": "regulator",
        "weight": 2,
    },
    {
        "name": "MAS (SG)",
        "url": "https://www.mas.gov.sg/news/rss",
        "type": "regulator",
        "weight": 2,
    },

    # === General fintech press ===
    {
        "name": "BBC Fintech",
        "url": "https://feeds.bbci.co.uk/news/topics/c5ggrnqz6w9t/rss.xml",
        "type": "press",
        "weight": 2,
    },
    {
        "name": "FT Fintech",
        "url": "https://www.ft.com/fintech?format=rss",
        "type": "press",
        "weight": 3,
    },
    {
        "name": "TechCrunch Fintech",
        "url": "https://techcrunch.com/category/fintech/feed/",
        "type": "press",
        "weight": 2,
    },

    # === Crypto press ===
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "type": "press",
        "weight": 2,
    },
    {
        "name": "The Block",
        "url": "https://www.theblock.co/rss.xml",
        "type": "press",
        "weight": 2,
    },
    {
        "name": "Cointelegraph",
        "url": "https://cointelegraph.com/rss",
        "type": "press",
        "weight": 1,
    },
    {
        "name": "Decrypt",
        "url": "https://decrypt.co/feed",
        "type": "press",
        "weight": 1,
    },

    # === Payments / fintech press ===
    {
        "name": "Finextra",
        "url": "https://www.finextra.com/rss/headlines.aspx",
        "type": "press",
        "weight": 2,
    },
    {
        "name": "PYMNTS",
        "url": "https://www.pymnts.com/feed/",
        "type": "press",
        "weight": 2,
    },
    {
        "name": "The Paypers",
        "url": "https://thepaypers.com/rss",
        "type": "press",
        "weight": 1,
    },

    # === Gambling / iGaming (filtered: only payments/licensing/financial) ===
    {
        "name": "iGaming Business",
        "url": "https://igamingbusiness.com/feed/",
        "type": "industry",
        "weight": 2,
    },
    {
        "name": "SBC News",
        "url": "https://sbcnews.co.uk/feed",
        "type": "industry",
        "weight": 1,
    },
    {
        "name": "Gambling Insider",
        "url": "https://www.gamblinginsider.com/feed",
        "type": "industry",
        "weight": 1,
    },
    {
        "name": "Gambling News",
        "url": "https://www.gamblingnews.com/feed/",
        "type": "industry",
        "weight": 1,
    },

    # === AML / Compliance ===
    {
        "name": "AML Intelligence",
        "url": "https://www.amlintelligence.com/feed/",
        "type": "industry",
        "weight": 2,
    },
    {
        "name": "AML Watcher",
        "url": "https://amlwatcher.com/news/feed/",
        "type": "industry",
        "weight": 1,
    },
]


# Sources without RSS — TODO add HTML scrapers later:
# - OFAC (Recent Actions)
# - VARA (Dubai)
# - DFSA (DIFC)
# - CySEC announcements
# - MFSA news
# - Forbes.ru fintech tag (https://www.forbes.ru/tegi/finteh) — no RSS
# - ACAMS news (https://www.acams.org/en/news) — no RSS


def domain_of(source_name: str, url: str) -> str:
    """Used for independence check. Different domains = independent sources."""
    from urllib.parse import urlparse
    return urlparse(url).netloc.lower().replace("www.", "")
