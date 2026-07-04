"""
VOID RSS News Cache
===================

SQLite-backed article cache with deduplication, full-text search,
and FIFO eviction (max 1 000 articles).

Database: memory/data/rss_cache.db

Schema:
    articles(id, url_hash, title, url, summary, source, category,
             published_at, tags, fetched_at)
"""

import hashlib
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("void.news.rss_cache")

_ROOT = Path(__file__).parent.parent
DB_FILE = _ROOT / "memory" / "data" / "rss_cache.db"
MAX_ARTICLES = 1000


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash     TEXT    NOT NULL UNIQUE,
    title        TEXT    NOT NULL,
    url          TEXT    NOT NULL,
    summary      TEXT    DEFAULT '',
    source       TEXT    DEFAULT '',
    category     TEXT    DEFAULT 'general',
    published_at TEXT    DEFAULT '',
    tags         TEXT    DEFAULT '',
    fetched_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_category  ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_fetched   ON articles(fetched_at);
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, summary, source, content='articles', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary, source)
    VALUES (new.id, new.title, new.summary, new.source);
END;
CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, source)
    VALUES ('delete', old.id, old.title, old.summary, old.source);
END;
"""


class RSSCache:
    """Thread-safe SQLite cache for RSS articles."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        logger.info(f"[RSS-CACHE] Initialised DB at {self.db_path}")

    @staticmethod
    def _url_hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def _evict_if_needed(self, conn: sqlite3.Connection) -> None:
        """Remove oldest articles when limit is exceeded."""
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        if count >= MAX_ARTICLES:
            excess = count - MAX_ARTICLES + 1
            conn.execute(
                "DELETE FROM articles WHERE id IN "
                "(SELECT id FROM articles ORDER BY fetched_at ASC LIMIT ?)",
                (excess,),
            )
            logger.info(f"[RSS-CACHE] Evicted {excess} old articles (limit={MAX_ARTICLES})")

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------
    def upsert(self, article: Dict[str, Any]) -> bool:
        """
        Insert or ignore an article (deduplication by URL hash).

        Returns True if the article was newly inserted, False if duplicate.
        """
        url = article.get("url", "")
        if not url:
            return False

        url_hash = self._url_hash(url)
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            with self._connect() as conn:
                self._evict_if_needed(conn)
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO articles
                        (url_hash, title, url, summary, source, category,
                         published_at, tags, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        url_hash,
                        article.get("title", "Untitled"),
                        url,
                        article.get("summary", ""),
                        article.get("source", ""),
                        article.get("category", "general"),
                        article.get("published_at", ""),
                        ",".join(article.get("tags", [])),
                        now,
                    ),
                )
                return cursor.rowcount > 0

    def upsert_many(self, articles: List[Dict[str, Any]]) -> int:
        """Bulk upsert, returns count of newly inserted articles."""
        return sum(1 for a in articles if self.upsert(a))

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------
    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the n most recently fetched articles."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles ORDER BY fetched_at DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_category(self, category: str, n: int = 10) -> List[Dict[str, Any]]:
        """Return the n most recent articles in a given category."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles WHERE category = ? "
                "ORDER BY fetched_at DESC LIMIT ?",
                (category.lower(), n),
            ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, n: int = 10) -> List[Dict[str, Any]]:
        """Full-text search across title, summary, and source."""
        if not query.strip():
            return self.get_recent(n)
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT a.* FROM articles a
                    JOIN articles_fts f ON a.id = f.rowid
                    WHERE articles_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, n),
                ).fetchall()
            except sqlite3.OperationalError:
                # FTS not available — fall back to LIKE search
                rows = conn.execute(
                    "SELECT * FROM articles "
                    "WHERE title LIKE ? OR summary LIKE ? "
                    "ORDER BY fetched_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", n),
                ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        """Total number of cached articles."""
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    def sources(self) -> List[str]:
        """List all distinct source names in cache."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT source FROM articles ORDER BY source"
            ).fetchall()
        return [r[0] for r in rows]

    def status(self) -> Dict[str, Any]:
        """Return cache status for monitoring dashboard."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            last = conn.execute(
                "SELECT fetched_at FROM articles ORDER BY fetched_at DESC LIMIT 1"
            ).fetchone()
            by_source = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM articles "
                "GROUP BY source ORDER BY cnt DESC"
            ).fetchall()
        return {
            "total_articles": total,
            "max_articles": MAX_ARTICLES,
            "last_fetch": last[0] if last else None,
            "by_source": {r[0]: r[1] for r in by_source},
        }
