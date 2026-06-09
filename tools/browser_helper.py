import os
import subprocess
import logging
import requests
import re
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import quote_plus

logger = logging.getLogger("void.browser_helper")

def open_tabs(count: int, topic: str) -> Dict[str, Any]:
    """
    Open multiple tabs in Chrome about a specific topic.
    Generates high-quality relevant URLs and opens them simultaneously.
    """
    topic_clean = topic.strip()
    topic_encoded = quote_plus(topic_clean)
    
    # Base resource URLs based on the topic
    urls = [
        f"https://www.google.com/search?q={topic_encoded}",
        f"https://www.google.com/search?q={topic_encoded}+startup+competitors+market",
        f"https://news.ycombinator.com/item?id=3000000" if "startup" in topic.lower() else f"https://en.wikipedia.org/wiki/{topic_encoded}"
    ]
    
    # Expand URLs up to requested count
    extra_queries = [
        "latest+trends", "funding+news", "reddit+discussion",
        "market+size", "hacker+news", "product+hunt", "techcrunch"
    ]
    
    for idx in range(min(count - len(urls), len(extra_queries))):
        q = f"{topic_clean}+{extra_queries[idx]}"
        urls.append(f"https://www.google.com/search?q={quote_plus(q)}")
        
    # Cap total tabs at 10 to avoid system overload
    urls = urls[:min(count, 10)]
    
    try:
        # Spawn Chrome tabs simultaneously
        import webbrowser
        for url in urls:
            webbrowser.open(url)
        
        return {
            "status": "ok",
            "message": f"Successfully opened **{len(urls)} Chrome tabs** about **'{topic_clean}'**, Sir. Ready for your review."
        }
    except Exception as e:
        logger.error(f"Failed to open tabs: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to open tabs: {str(e)}"}

def research_competitors(query: str) -> Dict[str, Any]:
    """
    Perform automatic organic web research using DuckDuckGo HTML scraper.
    Extracts competitors and returns a formatted premium summary.
    """
    topic = query.strip()
    search_query = f"{topic} competitors alternative"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=6.0)
        if response.status_code != 200:
            # Fallback to direct Chrome portal
            import webbrowser
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(search_query)}")
            return {
                "status": "ok",
                "message": f"I couldn't fetch organic results directly, Sir. I have opened a Chrome research portal for **'{topic} competitors'** instead."
            }
            
        html = response.text
        
        # Simple extraction of organic results from DuckDuckGo HTML
        # Result blocks look like: <a class="result__snippet" ...>...</a>
        results = []
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
        titles = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', html, re.DOTALL)
        
        for idx in range(min(len(snippets), 4)):
            snippet_text = re.sub(r'<[^>]*>', '', snippets[idx]).strip()
            title_text = re.sub(r'<[^>]*>', '', titles[idx]).strip() if idx < len(titles) else "Resource"
            results.append(f"- **{title_text}**: {snippet_text}")
            
        if results:
            summary = "\n\n".join(results)
            return {
                "status": "ok",
                "message": f"Here is the competitive analysis summary for **'{topic}'**:\n\n{summary}"
            }
        else:
            import webbrowser
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(search_query)}")
            return {
                "status": "ok",
                "message": f"I initiated a Chrome research board for **'{topic} competitors'** to assist your evaluation, Sir."
            }
            
    except Exception as e:
        logger.error(f"Competitor research failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Research failed: {str(e)}"}

def download_file(url: str, target_folder: str = None) -> Dict[str, Any]:
    """
    Download a file programmatically from a URL.
    Saves to the user's Downloads directory by default.
    """
    try:
        user_profile = Path(os.environ.get("USERPROFILE", "C:\\"))
        download_dir = user_profile / "Downloads"
        if target_folder:
            target_path = Path(target_folder)
            if target_path.exists():
                download_dir = target_path
                
        # Resolve filename
        filename = url.split("/")[-1].split("?")[0]
        if not filename or not re.search(r'\.[a-zA-Z0-9]{2,4}$', filename):
            filename = "downloaded_file.pdf"
            
        dest_path = download_dir / filename
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=10.0)
        response.raise_for_status()
        
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        return {
            "status": "ok",
            "message": f"Successfully downloaded file to **{dest_path}**, Sir. File size: **{dest_path.stat().st_size / 1024:.1f} KB**."
        }
    except Exception as e:
        logger.error(f"File download failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to download: {str(e)}"}
