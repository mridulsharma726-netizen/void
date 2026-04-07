"""
VOID Web Intelligence Module
====================

Internet search, webpage reading, and information extraction.

Functions:
- search_web(query) -> dict
- read_page(url) -> dict
- summarize_text(text) -> str
- find_information(query) -> dict
"""

import webbrowser
import logging
import re
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus, urlparse

# Configure logging
logger = logging.getLogger("VOID-WebIntelligence")

# Default headers for requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def search_web(query: str, open_browser: bool = True) -> Dict[str, Any]:
    """
    Search the web using Google.
    
    Args:
        query: Search query
        open_browser: If True, open results in browser
        
    Returns:
        Dict with status, query, and search URL
    """
    query = query.strip()
    if not query:
        return {"status": "error", "message": "Empty query"}
    
    # Encode query for URL
    encoded_query = quote_plus(query)
    search_url = f"https://www.google.com/search?q={encoded_query}"
    
    logger.info(f"[WEB] Searching: {query}")
    
    if open_browser:
        try:
            webbrowser.open(search_url)
            return {
                "status": "ok",
                "query": query,
                "url": search_url,
                "message": f"Opened search results for: {query}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    return {
        "status": "ok",
        "query": query,
        "url": search_url
    }


def search_duckduckgo(query: str, open_browser: bool = True) -> Dict[str, Any]:
    """Search using DuckDuckGo (more privacy-focused)."""
    query = query.strip()
    if not query:
        return {"status": "error", "message": "Empty query"}
    
    encoded_query = quote_plus(query)
    search_url = f"https://duckduckgo.com/?q={encoded_query}"
    
    logger.info(f"[WEB] DuckDuckGo search: {query}")
    
    if open_browser:
        try:
            webbrowser.open(search_url)
            return {
                "status": "ok",
                "query": query,
                "url": search_url,
                "message": f"Opened DuckDuckGo results for: {query}"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return {"status": "ok", "query": query, "url": search_url}


def read_page(url: str, max_paragraphs: int = 10) -> Dict[str, Any]:
    """
    Read and extract text from a webpage.
    
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
    
    logger.info(f"[WEB] Reading: {url}")
    
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        
        # Simple HTML parsing without BeautifulSoup (to avoid dependency)
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
            if text and len(text) > 20:  # Skip very short texts
                clean_paragraphs.append(text)
        
        full_text = "\n\n".join(clean_paragraphs)
        
        return {
            "status": "ok",
            "url": url,
            "title": title,
            "paragraphs": len(clean_paragraphs),
            "text": full_text[:5000]  # Limit text length
        }
        
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Could not connect to URL"}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_page_summary(url: str) -> Dict[str, Any]:
    """
    Get a quick summary of a webpage (title + first few sentences).
    
    Args:
        url: Webpage URL
        
    Returns:
        Dict with summary info
    """
    result = read_page(url, max_paragraphs=3)
    
    if result["status"] != "ok":
        return result
    
    # Extract first 2-3 sentences
    text = result.get("text", "")
    sentences = re.split(r'[.!?]+', text)
    summary_sentences = []
    
    for sent in sentences[:3]:
        sent = sent.strip()
        if sent and len(sent) > 20:
            summary_sentences.append(sent)
    
    summary = ". ".join(summary_sentences)
    
    return {
        "status": "ok",
        "url": url,
        "title": result.get("title", "Unknown"),
        "summary": summary[:500],
        "full_text": text
    }


def search_and_read(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Search the web and read top results.
    
    Args:
        query: Search query
        max_results: Number of results to read
        
    Returns:
        Dict with search results and page contents
    """
    # First, search (opens browser)
    search_result = search_web(query, open_browser=True)
    
    if search_result["status"] != "ok":
        return search_result
    
    # For now, just return search info
    # Reading actual pages requires user to select a URL
    return {
        "status": "ok",
        "query": query,
        "search_url": search_result["url"],
        "message": f"Search opened. Want me to read a specific page? Just say 'read [url]'"
    }


def find_information(query: str) -> Dict[str, Any]:
    """
    Comprehensive information finding - search + suggest next steps.
    
    Args:
        query: User's information need
        
    Returns:
        Dict with action and suggestions
    """
    query_lower = query.lower()
    
    # Detect type of search
    is_news = any(word in query_lower for word in ["news", "latest", "recent"])
    is_howto = any(word in query_lower for word in ["how to", "howto", "tutorial", "guide"])
    is_product = any(word in query_lower for word in ["best", "top", "review", "compare"])
    is_definition = any(word in query_lower for word in ["what is", "define", "meaning of"])
    
    # Perform search
    result = search_web(query, open_browser=True)
    
    # Add context to result
    result["query_type"] = "general"
    if is_news:
        result["query_type"] = "news"
    elif is_howto:
        result["query_type"] = "howto"
    elif is_product:
        result["query_type"] = "product"
    elif is_definition:
        result["query_type"] = "definition"
    
    return result


def extract_links(html: str, base_url: str = "") -> List[str]:
    """Extract all links from HTML."""
    # Find all href attributes
    links = re.findall(r'href=["\']([^"\']+)["\']', html)
    
    # Clean and filter links
    clean_links = []
    for link in links:
        # Skip anchors, javascript, mailto
        if link.startswith(('#', 'javascript:', 'mailto:')):
            continue
        
        # Handle relative URLs
        if link.startswith('/'):
            if base_url:
                from urllib.parse import urljoin
                link = urljoin(base_url, link)
        
        # Only keep http(s) links
        if link.startswith('http'):
            clean_links.append(link)
    
    return clean_links[:20]  # Limit to 20 links


def get_favicon(url: str) -> Optional[str]:
    """Get the favicon URL for a website."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


def is_url(text: str) -> bool:
    """Check if text is a valid URL."""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(text))


# ============================================================================
# NATURAL LANGUAGE PARSING
# ============================================================================

def parse_search_command(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Parse natural language search commands.
    
    Handles:
    - "search [query]"
    - "find [information]"
    - "look up [topic]"
    - "search for [query]"
    """
    prompt_lower = prompt.lower().strip()
    
    # Patterns
    patterns = [
        r'^search\s+(.+)$',
        r'^search\s+for\s+(.+)$',
        r'^find\s+(.+)$',
        r'^look\s+up\s+(.+)$',
        r'^what\s+is\s+(.+)$',
        r'^how\s+to\s+(.+)$',
        r'^latest\s+(.+)$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, prompt_lower)
        if match:
            query = match.group(1).strip()
            return {
                "action": "search",
                "query": query
            }
    
    # Check for URL directly
    if is_url(prompt):
        return {
            "action": "read",
            "url": prompt
        }
    
    # Check for "read [url]" pattern
    if prompt_lower.startswith("read "):
        url = prompt[5:].strip()
        if url:
            return {
                "action": "read",
                "url": url
            }
    
    return None


# ============================================================================
# EXAMPLE USAGE FUNCTIONS
# ============================================================================

def quick_search(query: str) -> str:
    """Quick search with simple return message."""
    result = search_web(query)
    if result["status"] == "ok":
        return f"🔍 Searching for: {query}\nResults opened in browser."
    return f"❌ Search failed: {result.get('message', 'Unknown error')}"


def quick_read(url: str) -> str:
    """Quick read with summary."""
    result = get_page_summary(url)
    if result["status"] == "ok":
        title = result.get("title", "Unknown")
        summary = result.get("summary", "No summary available")
        return f"📄 {title}\n\n{summary}"
    return f"❌ Could not read page: {result.get('message', 'Unknown error')}"


if __name__ == "__main__":
    # Test web intelligence
    print("Testing web intelligence...")
    
    # Test search
    print("\n1. Search test:")
    result = search_web("python tutorial")
    print(f"Result: {result}")
    
    # Test URL detection
    print("\n2. URL detection:")
    print(f"  'https://google.com': {is_url('https://google.com')}")
    print(f"  'search python': {is_url('search python')}")
    
    # Test command parsing
    print("\n3. Command parsing:")
    print(f"  'search python': {parse_search_command('search python')}")
    print(f"  'read https://google.com': {parse_search_command('read https://google.com')}")

