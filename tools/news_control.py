import logging
from typing import Dict, Any, List

logger = logging.getLogger("void.news_control")

def get_recent_news(topic: str = None) -> Dict[str, Any]:
    """
    Retrieves recent headlines and articles by topic or category.
    Utilizes the cached RSS news engine database (no API key required).
    """
    try:
        from news.rss_engine import get_engine
        engine = get_engine()
        
        # If a specific topic query is provided, search articles
        if topic:
            logger.info(f"[NEWS] Querying cached articles for topic: {topic}")
            articles = engine.search_articles(topic, limit=10)
            if not articles:
                return {
                    "status": "ok",
                    "message": f"No recent news articles found matching topic **\"{topic}\"**, Sir.",
                    "data": []
                }
            
            summary_lines = [f"📰 **Recent News about \"{topic}\"**:\n"]
            for a in articles:
                summary_lines.append(f"- **{a.title}** (*{a.source}*)\n  {a.summary[:180]}...\n  Link: {a.url}")
                
            return {
                "status": "ok",
                "message": "\n".join(summary_lines),
                "data": [a.to_dict() for a in articles]
            }
            
        # Default: return recent news articles
        logger.info("[NEWS] Querying general recent cached articles")
        articles = engine.get_recent(limit=10)
        if not articles:
            return {
                "status": "ok",
                "message": "No news articles found in local cache, Sir.",
                "data": []
            }
            
        summary_lines = ["📰 **Latest News Headlines**:\n"]
        for a in articles:
            summary_lines.append(f"- **{a.title}** (*{a.source}*)\n  {a.summary[:180]}...\n  Link: {a.url}")
            
        return {
            "status": "ok",
            "message": "\n".join(summary_lines),
            "data": [a.to_dict() for a in articles]
        }
        
    except Exception as e:
        logger.error(f"[NEWS] Failed to retrieve news: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to retrieve news from cache: {str(e)}"}
