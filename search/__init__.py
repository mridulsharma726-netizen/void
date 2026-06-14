"""
VOID Search Module
==================
Provides zero-cost web search via DuckDuckGo (no API key required).
"""
from search.duckduckgo_provider import DuckDuckGoProvider, search

__all__ = ["DuckDuckGoProvider", "search"]
