"""
VOID Knowledge Fusion Layer
============================

Combines multiple information sources before sending context to the LLM:

  Sources fused:
    1. DuckDuckGo web search results
    2. RSS news articles (cached)
    3. Semantic memory facts (SQLite)
    4. Active project context (if available)

The fused prompt context is injected into the LLM system prompt so the
model reasons over real evidence instead of hallucinating.

Usage:
    from server.backend.knowledge_fusion import KnowledgeFusion, FusedContext

    fusion = KnowledgeFusion()
    ctx = fusion.fuse(
        query="Latest developments in quantum computing",
        requires_web=True,
        requires_news=True,
    )
    # ctx.combined_prompt → inject into LLM call
    # ctx.web_results     → list of DDG result dicts
    # ctx.news_articles   → list of Article dicts
    # ctx.memory_facts    → list of memory fact strings
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("void.knowledge_fusion")

# ---------------------------------------------------------------------------
# Fused context dataclass
# ---------------------------------------------------------------------------
@dataclass
class FusedContext:
    """Holds all fused information sources for a single query."""
    query: str
    web_results: List[Dict[str, Any]] = field(default_factory=list)
    news_articles: List[Dict[str, Any]] = field(default_factory=list)
    memory_facts: List[str] = field(default_factory=list)
    project_context: str = ""
    combined_prompt: str = ""
    latency_ms: float = 0.0
    sources_used: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt builder helpers
# ---------------------------------------------------------------------------
def _format_web_results(results: List[Dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = ["[WEB SEARCH RESULTS]"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. {r.get('title','?')} — {r.get('source','')}\n"
            f"   URL: {r.get('url','')}\n"
            f"   {r.get('snippet','')}"
        )
    return "\n".join(lines)


def _format_news(articles: List[Dict[str, Any]]) -> str:
    if not articles:
        return ""
    lines = ["[RECENT NEWS ARTICLES]"]
    for i, a in enumerate(articles, 1):
        pub = a.get("published_at", "") or a.get("fetched_at", "")
        pub_str = f" ({pub[:10]})" if pub else ""
        lines.append(
            f"{i}. [{a.get('source','?')}]{pub_str} {a.get('title','?')}\n"
            f"   {a.get('summary','')[:200]}"
        )
    return "\n".join(lines)


def _format_memory(facts: List[str]) -> str:
    if not facts:
        return ""
    lines = ["[MEMORY CONTEXT]"]
    for f in facts[:5]:
        lines.append(f"• {f}")
    return "\n".join(lines)


def _format_project(context: str) -> str:
    if not context:
        return ""
    return f"[PROJECT CONTEXT]\n{context[:800]}"


def _build_combined_prompt(
    query: str,
    web: str,
    news: str,
    memory: str,
    project: str,
) -> str:
    """Assemble the full context block injected above the user query."""
    sections = [s for s in [web, news, memory, project] if s]
    if not sections:
        return ""
    divider = "─" * 60
    body = f"\n{divider}\n".join(sections)
    return (
        f"{divider}\n"
        f"REAL-TIME CONTEXT FOR YOUR RESPONSE:\n"
        f"{divider}\n"
        f"{body}\n"
        f"{divider}\n"
        f"Use the above sources to answer accurately. "
        f"Cite sources when relevant. Do not hallucinate facts not present above.\n"
        f"{divider}"
    )


# ---------------------------------------------------------------------------
# Main fusion class
# ---------------------------------------------------------------------------
class KnowledgeFusion:
    """
    Orchestrates fetching and combining knowledge from multiple sources.
    Designed to be used as a singleton (see get_fusion()).
    """

    def __init__(self):
        self._ddg = None    # lazy
        self._rss = None    # lazy
        self._memory = None # lazy

    # ------------------------------------------------------------------
    # Lazy accessors
    # ------------------------------------------------------------------
    def _get_ddg(self):
        if self._ddg is None:
            try:
                from search.duckduckgo_provider import get_provider
                self._ddg = get_provider()
            except Exception as exc:
                logger.warning(f"[FUSION] DDG provider unavailable: {exc}")
        return self._ddg

    def _get_rss(self):
        if self._rss is None:
            try:
                from news.rss_engine import get_engine
                self._rss = get_engine()
            except Exception as exc:
                logger.warning(f"[FUSION] RSS engine unavailable: {exc}")
        return self._rss

    def _get_memory(self):
        if self._memory is None:
            try:
                from backend.memory_sqlite import semantic_search
                self._memory = semantic_search
            except Exception as exc:
                logger.warning(f"[FUSION] Memory unavailable: {exc}")
        return self._memory

    # ------------------------------------------------------------------
    # Individual source fetchers (safe — never raise)
    # ------------------------------------------------------------------
    def _fetch_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        ddg = self._get_ddg()
        if not ddg:
            return []
        try:
            return ddg.search(query, max_results=max_results)
        except Exception as exc:
            logger.warning(f"[FUSION] Web search error: {exc}")
            return []

    def _fetch_news_web(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """Fetch live news from DDG News tab."""
        ddg = self._get_ddg()
        if not ddg:
            return []
        try:
            return ddg.search_news(query, max_results=max_results)
        except Exception as exc:
            logger.warning(f"[FUSION] DDG news error: {exc}")
            return []

    def _fetch_news_rss(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Fetch news from local RSS cache."""
        rss = self._get_rss()
        if not rss:
            return []
        try:
            articles = rss.search_articles(query, n=max_results)
            return [a.to_dict() for a in articles]
        except Exception as exc:
            logger.warning(f"[FUSION] RSS search error: {exc}")
            return []

    def _fetch_memory(self, query: str) -> List[str]:
        """Retrieve semantically relevant memory facts."""
        fn = self._get_memory()
        if not fn:
            return []
        try:
            results = fn(query, top_k=5)
            if isinstance(results, list):
                facts = []
                for r in results:
                    if isinstance(r, dict):
                        facts.append(r.get("fact") or r.get("content") or str(r))
                    else:
                        facts.append(str(r))
                return facts
        except Exception as exc:
            logger.warning(f"[FUSION] Memory retrieval error: {exc}")
        return []

    def _fetch_project_context(self) -> str:
        """Retrieve active project summary if available."""
        try:
            from tools.project_intelligence import get_active_project_summary
            return get_active_project_summary() or ""
        except Exception:
            pass
        try:
            from backend.project_analyzer import get_current_project_summary
            return get_current_project_summary() or ""
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Main fusion entry point
    # ------------------------------------------------------------------
    def fuse(
        self,
        query: str,
        requires_web: bool = False,
        requires_news: bool = False,
        requires_project: bool = False,
        web_results: int = 5,
        news_results: int = 5,
    ) -> FusedContext:
        """
        Gather and fuse all relevant knowledge sources for the given query.

        Args:
            query:            User's query text.
            requires_web:     Include DuckDuckGo web search results.
            requires_news:    Include RSS + DDG News results.
            requires_project: Include active project context.
            web_results:      Max web results to fetch (default 5).
            news_results:     Max news items to fetch (default 5).

        Returns:
            FusedContext with all gathered data and a combined_prompt string.
        """
        t0 = time.perf_counter()
        ctx = FusedContext(query=query)
        sources_used: List[str] = []

        logger.info(
            f"[FUSION] Fusing context for: '{query[:60]}' "
            f"(web={requires_web}, news={requires_news}, project={requires_project})"
        )

        # --- Memory (always fetched) ---
        ctx.memory_facts = self._fetch_memory(query)
        if ctx.memory_facts:
            sources_used.append("memory")

        # --- Web search ---
        if requires_web:
            ctx.web_results = self._fetch_web(query, web_results)
            if ctx.web_results:
                sources_used.append("web")

        # --- News ---
        if requires_news:
            # Combine RSS cache hits + live DDG News results
            rss_articles = self._fetch_news_rss(query, news_results)
            ddg_news = self._fetch_news_web(query, max(0, news_results - len(rss_articles)))
            ctx.news_articles = rss_articles + [
                a for a in ddg_news
                if not any(r.get("url") == a.get("url") for r in rss_articles)
            ]
            if ctx.news_articles:
                sources_used.append("news")

        # --- Project context ---
        if requires_project:
            ctx.project_context = self._fetch_project_context()
            if ctx.project_context:
                sources_used.append("project")

        # --- Build combined prompt ---
        web_str     = _format_web_results(ctx.web_results)
        news_str    = _format_news(ctx.news_articles)
        memory_str  = _format_memory(ctx.memory_facts)
        project_str = _format_project(ctx.project_context)

        ctx.combined_prompt = _build_combined_prompt(
            query, web_str, news_str, memory_str, project_str
        )
        ctx.latency_ms = (time.perf_counter() - t0) * 1000
        ctx.sources_used = sources_used

        logger.info(
            f"[FUSION] Done in {ctx.latency_ms:.0f}ms — "
            f"sources: {sources_used}"
        )
        return ctx

    def status(self) -> Dict[str, Any]:
        """Return fusion layer status for the monitoring dashboard."""
        ddg = self._get_ddg()
        rss = self._get_rss()
        return {
            "search": ddg.status() if ddg else {"status": "unavailable"},
            "rss": rss.status() if rss else {"status": "unavailable"},
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_fusion: Optional[KnowledgeFusion] = None

def get_fusion() -> KnowledgeFusion:
    """Return (or create) the module-level KnowledgeFusion singleton."""
    global _fusion
    if _fusion is None:
        _fusion = KnowledgeFusion()
    return _fusion
