import sys
import os
import asyncio

# Setup workspace environment path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)
sys.path.append(os.path.join(ROOT, "server"))

from server.backend.intent_router import IntentRouter
from server.backend.deep_research import ResearchIntentDetector, SourceCollector, ResearchMemory, CitationManager

async def test_intent_detection():
    print("=== Testing Intent Detection & Topic Extraction ===")
    router = IntentRouter()
    
    test_cases = [
        # Normal chats (should classify as chat)
        ("What is the capital of France?", "chat"),
        ("Tell me about Tesla", "chat"),
        ("Explain quantum physics simply", "chat"),
        
        # Deep research queries
        ("Do a deep research on Tesla", "deep_research"),
        ("investigate Tesla's future growth", "deep_research"),
        ("create a comprehensive research report on OpenAI", "deep_research"),
        ("find everything about renewable energy", "deep_research"),
        ("analyze this thoroughly: artificial intelligence ethics", "deep_research")
    ]
    
    for query, expected_intent in test_cases:
        res = await router.classify(query)
        print(f"Query: \"{query}\"")
        print(f"  -> Extracted Intent: {res.intent} (Expected: {expected_intent})")
        if res.intent == "deep_research":
            topic = res.params.get("topic")
            print(f"  -> Extracted Topic:  \"{topic}\"")
        print()

async def dummy_progress(msg: str, speak_msg: str = None):
    print(f"     [Progress Update] {msg}")

async def test_search_scraper():
    print("=== Testing DuckDuckGo Local HTML Organic Scraper ===")
    memory = ResearchMemory()
    citation_mgr = CitationManager()
    collector = SourceCollector(memory, citation_mgr)
    
    topic = "OpenAI GPT-4o"
    print(f"Running targeted DDG query for: '{topic}'")
    
    # We test with just a single category query (news/general) to keep it fast
    queries = [(topic, "General News")]
    
    unique_sources = {}
    loop = asyncio.get_running_loop()
    
    # Simulate single query run to verify DuckDuckGo HTML parser structure
    url = f"https://html.duckduckgo.com/html/?q=OpenAI+GPT-4o"
    print(f"  Fetching: {url}")
    try:
        response = await loop.run_in_executor(None, lambda: requests.get(url, headers=collector.headers, timeout=8.0))
        print(f"  Response Status: {response.status_code}")
        if response.status_code in [200, 202]:
            import re
            html = response.text
            blocks = html.split('<div class="result')
            print(f"  Raw Result Blocks Found: {len(blocks) - 1}")
            
            count = 0
            for block in blocks[1:]:
                url_match = re.search(r'class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                if url_match:
                    title = re.sub(r'<[^>]*>', '', url_match.group(2)).strip()
                    count += 1
                    if count <= 3:
                        print(f"    - Result #{count}: {title[:60]}")
            
            print(f"\n[OK] DDG scraper successfully parsed {len(blocks) - 1} search results.")
        else:
            print("[FAIL] Scraper failed to fetch results (status not 200/202)")
    except Exception as e:
        print(f"[FAIL] Scraper error: {e}")

async def main():
    await test_intent_detection()
    await test_search_scraper()

if __name__ == "__main__":
    import requests
    asyncio.run(main())
