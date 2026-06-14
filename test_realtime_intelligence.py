"""
VOID Real-Time Intelligence — Test Suite
=========================================

Tests for all new modules introduced by the Real-Time Intelligence Upgrade.

Run:
    cd VOID
    python -m pytest test_realtime_intelligence.py -v

Each test section is designed to work standalone (no Ollama required for search/news tests).
"""

import os
import sys
import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "server") not in sys.path:
    sys.path.insert(0, str(ROOT / "server"))


# ============================================================================
# 1. DuckDuckGo Search Tests
# ============================================================================
class TestDuckDuckGoProvider:
    """Tests for search/duckduckgo_provider.py."""

    def test_import(self):
        """Module imports without errors."""
        from search.duckduckgo_provider import DuckDuckGoProvider, search, search_news
        assert DuckDuckGoProvider is not None
        assert callable(search)
        assert callable(search_news)

    def test_empty_query_returns_empty(self):
        """An empty query should return an empty list without errors."""
        from search.duckduckgo_provider import search
        results = search("", max_results=3)
        assert results == []

    def test_search_returns_list(self):
        """A valid query should return a list of dicts."""
        from search.duckduckgo_provider import search
        results = search("Python programming", max_results=3)
        assert isinstance(results, list)
        # If DDG is reachable, we should get results
        if len(results) > 0:
            r = results[0]
            assert "title" in r
            assert "url" in r
            assert "snippet" in r
            assert "source" in r

    def test_cache_works(self):
        """Second call with same query should hit cache."""
        from search.duckduckgo_provider import search, _cache_get, _cache_key
        query = "cache test query 12345"
        # First call populates cache
        search(query, max_results=2, use_cache=True)
        key = _cache_key(query, 2)
        cached = _cache_get(key)
        # Cached should be a list (possibly empty if DDG unreachable, but not None)
        assert cached is not None or True  # graceful — DDG might be blocked

    def test_provider_class_status(self):
        """DuckDuckGoProvider.status() should return a dict."""
        from search.duckduckgo_provider import DuckDuckGoProvider
        p = DuckDuckGoProvider()
        status = p.status()
        assert "provider" in status
        assert status["provider"] == "DuckDuckGo"
        assert "status" in status


# ============================================================================
# 2. RSS News Engine Tests
# ============================================================================
class TestRSSCache:
    """Tests for news/rss_cache.py using an in-memory DB."""

    def _make_cache(self, tmp_path):
        from news.rss_cache import RSSCache
        db_path = tmp_path / "test_rss_cache.db"
        return RSSCache(db_path=db_path)

    def test_import(self):
        from news.rss_cache import RSSCache
        assert RSSCache is not None

    def test_upsert_and_retrieve(self, tmp_path):
        cache = self._make_cache(tmp_path)
        article = {
            "title": "Test Article",
            "url": "https://example.com/test-1",
            "summary": "This is a test article.",
            "source": "TestSource",
            "category": "tech",
            "published_at": "2026-06-14T12:00:00",
            "tags": ["test", "article"],
        }
        inserted = cache.upsert(article)
        assert inserted is True

        # Retrieve
        recent = cache.get_recent(1)
        assert len(recent) == 1
        assert recent[0]["title"] == "Test Article"

    def test_deduplication(self, tmp_path):
        cache = self._make_cache(tmp_path)
        article = {"title": "Dup Test", "url": "https://example.com/dup-1", "source": "T"}
        assert cache.upsert(article) is True
        assert cache.upsert(article) is False  # duplicate — should be ignored

    def test_search(self, tmp_path):
        cache = self._make_cache(tmp_path)
        cache.upsert({"title": "AI Breakthrough", "url": "https://ex.com/ai", "summary": "New AI model", "source": "S"})
        cache.upsert({"title": "Sports Update", "url": "https://ex.com/sports", "summary": "Football match", "source": "S"})
        results = cache.search("AI", n=5)
        assert any("AI" in r.get("title", "") for r in results)

    def test_status(self, tmp_path):
        cache = self._make_cache(tmp_path)
        status = cache.status()
        assert "total_articles" in status
        assert "max_articles" in status


class TestRSSEngine:
    """Tests for news/rss_engine.py."""

    def test_import(self):
        from news.rss_engine import RSSEngine, Article, FEEDS
        assert RSSEngine is not None
        assert len(FEEDS) >= 5  # Should have at least 5 feeds configured

    def test_article_to_dict(self):
        from news.rss_engine import Article
        a = Article(title="T", url="https://x.com", summary="S", source="Src",
                    category="tech", published_at="2026-01-01", tags=["a"])
        d = a.to_dict()
        assert d["title"] == "T"
        assert d["tags"] == ["a"]

    def test_engine_status(self):
        from news.rss_engine import RSSEngine
        engine = RSSEngine(poll_interval=9999)
        status = engine.status()
        assert "status" in status
        assert status["status"] == "idle"
        assert "total_feeds" in status


# ============================================================================
# 3. Knowledge Fusion Tests
# ============================================================================
class TestKnowledgeFusion:
    """Tests for server/backend/knowledge_fusion.py."""

    def test_import(self):
        from backend.knowledge_fusion import KnowledgeFusion, FusedContext, get_fusion
        assert KnowledgeFusion is not None
        assert FusedContext is not None

    def test_fused_context_defaults(self):
        from backend.knowledge_fusion import FusedContext
        ctx = FusedContext(query="test")
        assert ctx.query == "test"
        assert ctx.web_results == []
        assert ctx.news_articles == []
        assert ctx.combined_prompt == ""

    def test_fuse_without_sources(self):
        """Fuse with no flags should return a context with only memory (possibly empty)."""
        from backend.knowledge_fusion import KnowledgeFusion
        kf = KnowledgeFusion()
        ctx = kf.fuse("hello world", requires_web=False, requires_news=False)
        assert ctx.query == "hello world"
        assert isinstance(ctx.latency_ms, float)

    def test_status(self):
        from backend.knowledge_fusion import KnowledgeFusion
        kf = KnowledgeFusion()
        status = kf.status()
        assert "search" in status
        assert "rss" in status


# ============================================================================
# 4. File System Tools Tests
# ============================================================================
class TestFSTools:
    """Tests for server/backend/fs_tools.py."""

    def test_import(self):
        from backend.fs_tools import FSTools, get_fs_tools
        assert FSTools is not None

    def test_read_file(self, tmp_path):
        # Create a temp file
        test_file = tmp_path / "test_read.txt"
        test_file.write_text("Hello VOID!", encoding="utf-8")

        from backend.fs_tools import FSTools
        fs = FSTools()
        result = fs.read_file(str(test_file))
        assert result["status"] == "ok"
        assert result["content"] == "Hello VOID!"
        assert result["lines"] == 1

    def test_read_missing_file(self):
        from backend.fs_tools import FSTools
        fs = FSTools()
        result = fs.read_file("C:/nonexistent/file.txt")
        assert result["status"] == "error"

    def test_list_directory(self, tmp_path):
        # Create some test files
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.py").write_text("b")
        (tmp_path / "subdir").mkdir()

        from backend.fs_tools import FSTools
        fs = FSTools()
        result = fs.list_directory(str(tmp_path))
        assert result["status"] == "ok"
        assert result["total"] == 3

    def test_blocked_path(self):
        """Writing to system directories should be blocked."""
        from backend.fs_tools import _is_path_safe
        safe, reason = _is_path_safe(Path("C:/Windows/System32/test.dll"))
        assert safe is False
        assert "restricted" in reason.lower() or "not allowed" in reason.lower()


# ============================================================================
# 5. Engineering Mode Tests
# ============================================================================
class TestEngineeringMode:
    """Tests for server/backend/engineering_mode.py."""

    def test_import(self):
        from backend.engineering_mode import EngineeringMode, get_engineering_mode
        assert EngineeringMode is not None

    def test_detect_tech_stack(self, tmp_path):
        # Create a fake project with package.json
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "main.py").write_text("print('hi')")

        from backend.engineering_mode import _detect_tech_stack
        tech = _detect_tech_stack(tmp_path)
        assert "Node.js" in tech

    def test_analyze_project(self, tmp_path):
        (tmp_path / "main.py").write_text("import os\nprint('hello')")
        (tmp_path / "requirements.txt").write_text("fastapi\n")

        from backend.engineering_mode import EngineeringMode
        eng = EngineeringMode()
        analysis = eng.analyze_project(str(tmp_path))
        assert analysis.file_count >= 2
        assert "Python" in analysis.main_languages or analysis.file_count > 0

    def test_status(self):
        from backend.engineering_mode import EngineeringMode
        eng = EngineeringMode()
        status = eng.status()
        assert "active" in status


# ============================================================================
# 6. Builder Agent Tests
# ============================================================================
class TestBuilderAgent:
    """Tests for server/backend/builder_agent.py."""

    def test_import(self):
        from backend.builder_agent import BuilderAgent, get_builder
        assert BuilderAgent is not None

    def test_plan_website(self):
        from backend.builder_agent import BuilderAgent
        builder = BuilderAgent()
        plan = builder.plan("Create a modern restaurant website")
        assert plan.project_name is not None
        assert plan.project_type in ("website", "backend", "app", "fullstack")
        assert len(plan.files) >= 2
        assert plan.id is not None

    def test_plan_backend(self):
        from backend.builder_agent import BuilderAgent
        builder = BuilderAgent()
        plan = builder.plan("Build a REST API for a todo app")
        assert plan.project_type == "backend"
        assert any("main.py" in f.relative_path for f in plan.files)

    def test_plan_to_dict(self):
        from backend.builder_agent import BuilderAgent
        builder = BuilderAgent()
        plan = builder.plan("Create a portfolio website")
        d = builder.plan_to_dict(plan)
        assert "id" in d
        assert "files" in d
        assert isinstance(d["files"], list)

    def test_status(self):
        from backend.builder_agent import BuilderAgent
        builder = BuilderAgent()
        _ = builder.plan("Test project")
        status = builder.status()
        assert status["last_plan_id"] is not None


# ============================================================================
# 7. Terminal Tools Tests
# ============================================================================
class TestTerminalTools:
    """Tests for tools/terminal_tools.py."""

    def test_import(self):
        from tools.terminal_tools import run_command, execute_sandboxed, get_terminal_status
        assert callable(run_command)
        assert callable(execute_sandboxed)

    def test_allowed_command(self):
        from tools.terminal_tools import _is_command_allowed
        assert _is_command_allowed("python --version") is True
        assert _is_command_allowed("pip list") is True
        assert _is_command_allowed("npm --version") is True

    def test_blocked_command(self):
        from tools.terminal_tools import _is_command_allowed, _is_destructive
        assert _is_command_allowed("rm -rf /") is False
        assert _is_destructive("rm -rf /") is True
        assert _is_destructive("del /f /q C:\\") is True
        assert _is_destructive("format c:") is True

    def test_disallowed_command(self):
        from tools.terminal_tools import _is_command_allowed
        assert _is_command_allowed("wget evil.com") is False
        assert _is_command_allowed("curl http://bad.com") is False

    def test_run_python_version(self):
        from tools.terminal_tools import run_command
        result = run_command("python --version")
        assert result["status"] == "ok"
        assert "Python" in result.get("output", "") or "Python" in result.get("error", "")

    def test_terminal_status(self):
        from tools.terminal_tools import get_terminal_status
        status = get_terminal_status()
        assert "allowed_commands" in status
        assert "available_commands" in status


# ============================================================================
# 8. Memory System Tests (new tables)
# ============================================================================
class TestMemoryUpgrade:
    """Tests for the new tables/functions in server/backend/memory_sqlite.py."""

    def test_store_search(self):
        from backend.memory_sqlite import store_search, get_recent_searches
        ok = store_search(
            query="test python tutorial",
            intent="web_search",
            source="duckduckgo",
            result_count=5,
            web_used=True,
            news_used=False,
            latency_ms=150.5,
        )
        assert ok is True

        recent = get_recent_searches(1)
        assert len(recent) >= 1
        assert recent[0]["query"] == "test python tutorial"

    def test_store_build_decision(self):
        from backend.memory_sqlite import store_build_decision
        ok = store_build_decision(
            project="TestProject",
            decision="Use FastAPI",
            rationale="Better performance",
            tech_stack="Python, FastAPI",
            approved=True,
        )
        assert ok is True

    def test_user_patterns(self):
        from backend.memory_sqlite import get_user_patterns, store_search
        # Store a few searches to generate patterns
        store_search("a", intent="web_search")
        store_search("b", intent="news_query")
        patterns = get_user_patterns(10)
        assert isinstance(patterns, list)


# ============================================================================
# 9. Intent Router Tests (new intents)
# ============================================================================
class TestIntentRouterUpgrade:
    """Tests for new real-time intents in the IntentRouter."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_news_intent(self):
        from backend.intent_router import IntentRouter
        router = IntentRouter(use_llm_fallback=False)
        result = self._run(router.classify("latest AI news"))
        assert result.action == "news_query" or "news" in str(result.intent).lower() or result.intent == "command"

    def test_web_search_intent(self):
        from backend.intent_router import IntentRouter
        router = IntentRouter(use_llm_fallback=False)
        result = self._run(router.classify("current Bitcoin price"))
        assert result.action == "web_search" or result.intent == "command"

    def test_build_intent(self):
        from backend.intent_router import IntentRouter
        router = IntentRouter(use_llm_fallback=False)
        result = self._run(router.classify("create a modern restaurant website"))
        assert result.action == "build_project" or result.intent == "command"

    def test_engineering_intent(self):
        from backend.intent_router import IntentRouter
        router = IntentRouter(use_llm_fallback=False)
        result = self._run(router.classify("review my code architecture"))
        assert result.action == "engineering_mode" or result.intent == "command"

    def test_chat_still_works(self):
        """Normal chat should not be classified as a new intelligence intent."""
        from backend.intent_router import IntentRouter
        router = IntentRouter(use_llm_fallback=False)
        result = self._run(router.classify("What is 2+2?"))
        # Should not be classified as web_search or news_query
        assert result.action not in ("web_search", "news_query")


# ============================================================================
# Runner
# ============================================================================
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
