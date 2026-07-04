import logging
from typing import Dict, Any

logger = logging.getLogger("void.websearch_control")

def perform_web_search(query: str) -> Dict[str, Any]:
    """
    Performs a general web search fallback for questions using DuckDuckGo.
    Uses search.duckduckgo_provider (no API key required).
    """
    if not query or not query.strip():
        return {"status": "error", "message": "Search query cannot be empty, Sir."}
        
    query_clean = query.strip()
    try:
        logger.info(f"[WEBSEARCH] Performing DuckDuckGo search for: {query_clean}")
        from search.duckduckgo_provider import get_provider
        
        provider = get_provider()
        results = provider.search(query_clean, max_results=5)
        
        if not results:
            return {
                "status": "ok",
                "message": f"Search completed but no results were found for **\"{query_clean}\"**, Sir.",
                "data": []
            }
            
        summary_lines = [f"🔍 **Web Search Results for \"{query_clean}\"**:\n"]
        for r in results:
            summary_lines.append(f"- **{r.get('title', 'No Title')}** (*{r.get('source', '')}*)\n  {r.get('snippet', '')}\n  Link: {r.get('url', '')}")
            
        return {
            "status": "ok",
            "message": "\n".join(summary_lines),
            "data": results
        }
        
    except Exception as e:
        logger.error(f"[WEBSEARCH] Search execution failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Web search failed: {str(e)}"}
