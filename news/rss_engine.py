"""
VOID RSS News Engine
====================

Periodically fetches, parses, deduplicates and caches articles from
a curated list of open RSS/Atom feeds (no API keys required).

Feeds:
  BBC News          — http://feeds.bbci.co.uk/news/rss.xml
  BBC Technology    — http://feeds.bbci.co.uk/news/technology/rss.xml
  Reuters Tech      — https://feeds.reuters.com/reuters/technologyNews
  TechCrunch        — https://techcrunch.com/feed/
  Hacker News       — https://news.ycombinator.com/rss
  The Verge         — https://www.theverge.com/rss/index.xml
  AI Weekly         — https://aiweekly.co/issues.rss
  MIT Tech Review   — https://www.technologyreview.com/feed/

Usage:
    engine = get_engine()
    engine.start_background_fetch()          # starts polling thread
    articles = engine.fetch_all()            # manual fetch
    results  = engine.search_articles("AI") # query cached articles
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("void.news.rss_engine")

# ---------------------------------------------------------------------------
# Feed registry
# ---------------------------------------------------------------------------
FEEDS: List[Dict[str, str]] = [
    {
        "name": "BBC News",
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "category": "world",
        "fallback": "https://feeds.feedburner.com/BbcNews",
    },
    {
        "name": "BBC Technology",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "category": "tech",
        "fallback": "",
    },
    {
        "name": "Reuters Technology",
        "url": "https://feeds.reuters.com/reuters/technologyNews",
        "category": "tech",
        "fallback": "https://www.reuters.com/technology/rss.xml",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "tech",
        "fallback": "https://feeds.feedburner.com/TechCrunch",
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "category": "tech",
        "fallback": "",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "tech",
        "fallback": "",
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "ai",
        "fallback": "",
    },
    {
        "name": "AI Weekly",
        "url": "https://aiweekly.co/issues.rss",
        "category": "ai",
        "fallback": "",
    },
]

DEFAULT_POLL_INTERVAL = 900  # 15 minutes
REQUEST_TIMEOUT = 15         # seconds per feed


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Article:
    title: str
    url: str
    summary: str
    source: str
    category: str
    published_at: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "source": self.source,
            "category": self.category,
            "published_at": self.published_at,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# RSS Engine
# ---------------------------------------------------------------------------
class RSSEngine:
    """
    Fetches RSS/Atom feeds, parses articles, and stores them in RSSCache.

    Thread-safe; uses a background daemon thread for periodic polling.
    """

    def __init__(self, poll_interval: int = DEFAULT_POLL_INTERVAL):
        self.poll_interval = poll_interval
        self._cache = None          # lazy import to avoid circular imports
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_fetch: Optional[str] = None
        self._fetch_counts: Dict[str, int] = {}   # feed_name → articles fetched
        self._errors: Dict[str, str] = {}          # feed_name → last error msg

    # ------------------------------------------------------------------
    # Cache access (lazy)
    # ------------------------------------------------------------------
    def _get_cache(self):
        if self._cache is None:
            from news.rss_cache import RSSCache
            self._cache = RSSCache()
        return self._cache

    # ------------------------------------------------------------------
    # Feed parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_date(entry) -> str:
        """Parse a feedparser entry's published date to ISO-8601 string."""
        for attr in ("published_parsed", "updated_parsed", "created_parsed"):
            t = getattr(entry, attr, None)
            if t:
                try:
                    return datetime(*t[:6]).isoformat()
                except Exception:
                    pass
        return ""

    @staticmethod
    def _clean_html(raw: str) -> str:
        """Strip HTML tags from a string, falling back gracefully."""
        if not raw:
            return ""
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(raw, "html.parser").get_text(separator=" ").strip()
        except ImportError:
            import re
            return re.sub(r"<[^>]+>", " ", raw).strip()

    def _parse_feed(self, feed_meta: Dict[str, str]) -> List[Article]:
        """Fetch and parse a single RSS/Atom feed. Returns Article list."""
        import feedparser

        name = feed_meta["name"]
        urls_to_try = [feed_meta["url"]]
        if feed_meta.get("fallback"):
            urls_to_try.append(feed_meta["fallback"])

        for url in urls_to_try:
            try:
                logger.debug(f"[RSS] Fetching '{name}' from {url}")
                parsed = feedparser.parse(url, agent="VOID/2.0 RSS Reader", request_headers={
                    "Accept": "application/rss+xml, application/xml, text/xml"
                })

                if parsed.bozo and not parsed.entries:
                    logger.warning(f"[RSS] '{name}': bozo feed, skipping ({url})")
                    continue

                articles: List[Article] = []
                for entry in parsed.entries:
                    title = self._clean_html(getattr(entry, "title", "Untitled"))
                    link = getattr(entry, "link", "") or getattr(entry, "id", "")
                    if not link:
                        continue

                    # Summary: prefer summary over description
                    raw_summary = (
                        getattr(entry, "summary", "")
                        or getattr(entry, "description", "")
                    )
                    summary = self._clean_html(raw_summary)[:600]

                    # Tags/categories
                    tags: List[str] = []
                    for tag_obj in getattr(entry, "tags", []):
                        label = getattr(tag_obj, "term", "") or getattr(tag_obj, "label", "")
                        if label:
                            tags.append(label.lower().strip())

                    articles.append(Article(
                        title=title,
                        url=link,
                        summary=summary,
                        source=name,
                        category=feed_meta["category"],
                        published_at=self._parse_date(entry),
                        tags=tags[:5],
                    ))

                logger.info(f"[RSS] '{name}': parsed {len(articles)} articles")
                return articles

            except Exception as exc:
                logger.warning(f"[RSS] '{name}' at {url} failed: {exc}")
                self._errors[name] = str(exc)

        return []

    # ------------------------------------------------------------------
    # Public fetch API
    # ------------------------------------------------------------------
    def fetch_all(self) -> List[Article]:
        """
        Fetch all registered feeds right now.
        Stores results in the cache and returns all newly inserted articles.
        """
        logger.info(f"[RSS] Starting full fetch of {len(FEEDS)} feeds…")
        all_articles: List[Article] = []
        cache = self._get_cache()

        for feed_meta in FEEDS:
            articles = self._parse_feed(feed_meta)
            inserted = cache.upsert_many([a.to_dict() for a in articles])
            self._fetch_counts[feed_meta["name"]] = inserted
            all_articles.extend(articles)

        self._last_fetch = datetime.now(timezone.utc).isoformat()
        total = len(all_articles)
        logger.info(f"[RSS] Fetch complete — {total} articles processed")
        return all_articles

    def fetch_category(self, category: str) -> List[Article]:
        """
        Fetch only feeds matching a specific category, then return
        matching cached articles.
        """
        category = category.lower()
        matching_feeds = [f for f in FEEDS if f["category"] == category]
        if not matching_feeds:
            logger.warning(f"[RSS] No feeds for category '{category}'")

        cache = self._get_cache()
        for feed_meta in matching_feeds:
            articles = self._parse_feed(feed_meta)
            cache.upsert_many([a.to_dict() for a in articles])

        rows = cache.get_by_category(category, n=20)
        return [self._dict_to_article(r) for r in rows]

    def search_articles(self, query: str, n: int = 10) -> List[Article]:
        """
        Search cached articles using full-text search.
        Does NOT trigger a live fetch (use fetch_all() first if needed).
        """
        rows = self._get_cache().search(query, n)
        return [self._dict_to_article(r) for r in rows]

    def get_recent(self, n: int = 10) -> List[Article]:
        """Return the n most recently cached articles."""
        rows = self._get_cache().get_recent(n)
        return [self._dict_to_article(r) for r in rows]

    @staticmethod
    def _dict_to_article(d: Dict[str, Any]) -> Article:
        tags = d.get("tags", "")
        if isinstance(tags, str):
            tags = [t for t in tags.split(",") if t]
        return Article(
            title=d.get("title", ""),
            url=d.get("url", ""),
            summary=d.get("summary", ""),
            source=d.get("source", ""),
            category=d.get("category", "general"),
            published_at=d.get("published_at", ""),
            tags=tags,
        )

    # ------------------------------------------------------------------
    # Background polling
    # ------------------------------------------------------------------
    def start_background_fetch(self) -> None:
        """Start a daemon thread that polls all feeds every poll_interval seconds."""
        if self._thread and self._thread.is_alive():
            logger.info("[RSS] Background fetch thread already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="void-rss-poller",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"[RSS] Background fetch started (interval={self.poll_interval}s)"
        )

    def stop_background_fetch(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[RSS] Background fetch stopped")

    def _poll_loop(self) -> None:
        """Internal poll loop — runs in the background thread."""
        # Do an immediate fetch on startup
        try:
            self.fetch_all()
        except Exception as exc:
            logger.error(f"[RSS] Initial fetch failed: {exc}")

        while not self._stop_event.wait(timeout=self.poll_interval):
            try:
                self.fetch_all()
            except Exception as exc:
                logger.error(f"[RSS] Scheduled fetch failed: {exc}")

    # ------------------------------------------------------------------
    # Status / telemetry
    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        """Return engine status for the monitoring dashboard."""
        cache_status = self._get_cache().status()
        return {
            "status": "running" if (self._thread and self._thread.is_alive()) else "idle",
            "poll_interval_seconds": self.poll_interval,
            "last_fetch": self._last_fetch,
            "feed_counts": self._fetch_counts,
            "feed_errors": self._errors,
            "total_feeds": len(FEEDS),
            "cache": cache_status,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_engine: Optional[RSSEngine] = None

def get_engine(poll_interval: int = DEFAULT_POLL_INTERVAL) -> RSSEngine:
    """Return (or create) the module-level RSSEngine singleton."""
    global _engine
    if _engine is None:
        _engine = RSSEngine(poll_interval=poll_interval)
    return _engine


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== RSS Engine Self-Test ===")
    engine = RSSEngine()
    articles = engine.fetch_all()
    print(f"\nFetched {len(articles)} articles total")
    for a in articles[:3]:
        print(f"\n[{a.source}] {a.title}")
        print(f"  URL: {a.url}")
        print(f"  Summary: {a.summary[:100]}…")
    print("\n--- Search test: 'AI' ---")
    hits = engine.search_articles("AI", n=3)
    for h in hits:
        print(f"  [{h.source}] {h.title}")
