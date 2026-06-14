"""
VOID News Module
================
Provides real-time RSS feed ingestion, caching, and article search.
"""
from news.rss_engine import RSSEngine, Article, get_engine
from news.rss_cache import RSSCache

__all__ = ["RSSEngine", "Article", "RSSCache", "get_engine"]
