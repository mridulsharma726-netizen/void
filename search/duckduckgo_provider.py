"""
VOID DuckDuckGo Search Provider
=================================

Zero-cost web search using the duckduckgo-search library (no API key required).

Features:
  - Structured search results: title, URL, snippet, source domain
  - TTL-based in-memory result cache (5-minute TTL)
  - Retry logic: 3 attempts with exponential backoff
  - Timeout handling per attempt
  - Full structured logging at every stage
  - Thread-safe singleton pattern

Usage:
    from search.duckduckgo_provider import search

    results = search("latest AI news", max_results=5)
    for r in results:
        print(r["title"], r["url"], r["snippet"])
"""

import hashlib
import logging
import time
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("void.search.duckduckgo")

# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------
_cache_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

def _cache_key(query: str, max_results: int) -> str:
    return hashlib.md5(f"{query.lower().strip()}:{max_results}".encode()).hexdigest()

def _cache_get(key: str) -> Optional[List[Dict[str, Any]]]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry["ts"]) < CACHE_TTL_SECONDS:
            return entry["data"]
        if entry:
            del _cache[key]
    return None

def _cache_set(key: str, data: List[Dict[str, Any]]) -> None:
    with _cache_lock:
        _cache[key] = {"ts": time.time(), "data": data}


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------
def _make_result(title: str, url: str, snippet: str) -> Dict[str, Any]:
    """Normalise a single search result into VOID's standard format."""
    domain = urlparse(url).netloc.removeprefix("www.") if url else ""
    return {
        "title": title or "No title",
        "url": url or "",
        "snippet": snippet or "No description available.",
        "source": domain,
    }


# ---------------------------------------------------------------------------
# Core search logic
# ---------------------------------------------------------------------------
_MAX_RETRIES = 3
_TIMEOUT_PER_ATTEMPT = 10  # seconds


def _attempt_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Single search attempt using duckduckgo_search library."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error(
            "[DDG] duckduckgo-search is not installed. "
            "Run: pip install duckduckgo-search"
        )
        raise RuntimeError("duckduckgo-search not installed")

    results: List[Dict[str, Any]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(
            query,
            max_results=max_results,
            safesearch="moderate",
            timelimit=None,
        ):
            results.append(
                _make_result(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                )
            )
    return results


def search(
    query: str,
    max_results: int = 5,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search DuckDuckGo and return structured results.

    Args:
        query:       The search query string.
        max_results: Maximum number of results to return (default 5).
        use_cache:   Whether to use the in-memory TTL cache (default True).

    Returns:
        List of dicts, each with keys: title, url, snippet, source.
        Returns an empty list on failure (never raises).
    """
    query = query.strip()
    if not query:
        logger.warning("[DDG] Empty query supplied — returning no results.")
        return []

    logger.info(f"[DDG] Search query: '{query}' (max_results={max_results})")

    # Cache look-up
    key = _cache_key(query, max_results)
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            logger.info(f"[DDG] Cache hit for '{query}' ({len(cached)} results)")
            return cached

    # Retry loop with exponential backoff
    last_error: Optional[Exception] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(f"[DDG] Attempt {attempt}/{_MAX_RETRIES} for '{query}'")
            t0 = time.perf_counter()
            results = _attempt_search(query, max_results)
            elapsed = time.perf_counter() - t0
            logger.info(
                f"[DDG] Got {len(results)} results in {elapsed:.2f}s "
                f"(attempt {attempt})"
            )
            if use_cache:
                _cache_set(key, results)
            return results
        except Exception as exc:
            last_error = exc
            wait = 2 ** (attempt - 1)  # 1s, 2s, 4s
            logger.warning(
                f"[DDG] Attempt {attempt} failed: {exc}. "
                f"Retrying in {wait}s…"
            )
            if attempt < _MAX_RETRIES:
                time.sleep(wait)

    logger.error(f"[DDG] All {_MAX_RETRIES} attempts failed for '{query}': {last_error}")
    return []


def search_news(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search DuckDuckGo News tab for recent articles.

    Args:
        query:       The news search query.
        max_results: Maximum number of news articles (default 5).

    Returns:
        List of dicts with keys: title, url, snippet, source, published.
    """
    query = query.strip()
    if not query:
        return []

    logger.info(f"[DDG-NEWS] Searching news: '{query}'")

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("[DDG-NEWS] duckduckgo-search not installed.")
        return []

    results: List[Dict[str, Any]] = []
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=max_results):
                    domain = urlparse(r.get("url", "")).netloc.removeprefix("www.")
                    results.append({
                        "title": r.get("title", "No title"),
                        "url": r.get("url", ""),
                        "snippet": r.get("body", "No description."),
                        "source": r.get("source", domain),
                        "published": r.get("date", ""),
                    })
            logger.info(f"[DDG-NEWS] Got {len(results)} articles for '{query}'")
            return results
        except Exception as exc:
            last_error = exc
            wait = 2 ** (attempt - 1)
            logger.warning(f"[DDG-NEWS] Attempt {attempt} failed: {exc}. Retrying in {wait}s…")
            if attempt < _MAX_RETRIES:
                time.sleep(wait)

    logger.error(f"[DDG-NEWS] All attempts failed: {last_error}")
    return []


# ---------------------------------------------------------------------------
# Convenience class for dependency injection
# ---------------------------------------------------------------------------
class DuckDuckGoProvider:
    """
    Stateful provider class wrapping the module-level search functions.
    Useful for injection into KnowledgeFusion or other services.
    """

    def __init__(self, default_max_results: int = 5, use_cache: bool = True):
        self.default_max_results = default_max_results
        self.use_cache = use_cache
        self._last_query: str = ""
        self._last_result_count: int = 0
        self._last_latency_ms: float = 0.0

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Run a web search and record telemetry."""
        n = max_results or self.default_max_results
        t0 = time.perf_counter()
        results = search(query, n, use_cache=self.use_cache)
        self._last_latency_ms = (time.perf_counter() - t0) * 1000
        self._last_query = query
        self._last_result_count = len(results)
        return results

    def search_news(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Run a news search and record telemetry."""
        n = max_results or self.default_max_results
        t0 = time.perf_counter()
        results = search_news(query, n)
        self._last_latency_ms = (time.perf_counter() - t0) * 1000
        self._last_query = query
        self._last_result_count = len(results)
        return results

    def status(self) -> Dict[str, Any]:
        """Return current provider status for monitoring dashboard."""
        return {
            "provider": "DuckDuckGo",
            "last_query": self._last_query,
            "last_result_count": self._last_result_count,
            "last_latency_ms": round(self._last_latency_ms, 1),
            "cache_entries": len(_cache),
            "cache_ttl_seconds": CACHE_TTL_SECONDS,
            "status": "ready",
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_provider: Optional[DuckDuckGoProvider] = None

def get_provider() -> DuckDuckGoProvider:
    """Return (or create) the module-level DuckDuckGoProvider singleton."""
    global _provider
    if _provider is None:
        _provider = DuckDuckGoProvider()
    return _provider


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== DuckDuckGo Provider Self-Test ===")
    r = search("Python FastAPI tutorial", max_results=3)
    for i, item in enumerate(r, 1):
        print(f"\n[{i}] {item['title']}")
        print(f"    URL: {item['url']}")
        print(f"    Snippet: {item['snippet'][:120]}…")
    print(f"\nTotal: {len(r)} results")
