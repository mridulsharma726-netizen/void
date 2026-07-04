import logging
import re
import requests
from typing import Dict, Any

logger = logging.getLogger("void.websearch_control")

# Default headers for requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def read_page(url: str, max_paragraphs: int = 10) -> Dict[str, Any]:
    """
    Read and extract text from a webpage (without BeautifulSoup dependency).
    
    Args:
        url: Webpage URL
        max_paragraphs: Max paragraphs to extract
        
    Returns:
        Dict with status, title, text, and URL
    """
    if not url:
        return {"status": "error", "message": "Empty URL"}
    
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    logger.info(f"[WEBSEARCH] Reading: {url}")
    
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        
        html = response.text
        
        # Extract title
        title = ""
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
        
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract paragraphs
        paragraphs = re.findall(r'<p[^>]*>([^<]+)</p>', html, re.IGNORECASE)
        
        # Clean paragraph text
        clean_paragraphs = []
        for p in paragraphs[:max_paragraphs]:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', p)
            # Decode HTML entities
            text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
            text = text.replace('<', '<').replace('>', '>')
            text = text.replace('"', '"').replace('&#39;', "'")
            # Clean whitespace
            text = ' '.join(text.split())
            if text and len(text) > 20:
                clean_paragraphs.append(text)
        
        full_text = "\n\n".join(clean_paragraphs)
        
        return {
            "status": "ok",
            "url": url,
            "title": title,
            "paragraphs": len(clean_paragraphs),
            "text": full_text[:5000]
        }
        
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Could not connect to URL"}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except Exception as e:
        logger.error(f"[WEBSEARCH] Failed to read page {url}: {e}")
        return {"status": "error", "message": str(e)}

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
