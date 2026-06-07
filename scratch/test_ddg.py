import requests
import re
import html

url = "https://html.duckduckgo.com/html/"
data = {"q": "university accepting applications for bba"}
headers = {"User-Agent": "Mozilla/5.0"}

print("Sending POST request to DDG...")
r = requests.post(url, data=data, headers=headers, timeout=10)

results = []
blocks = re.split(r'<div class="[^"]*result__body[^"]*"', r.text)

print(f"Blocks found: {len(blocks)}")

# The first block is header, remaining are results
for block in blocks[1:]:
    # Extract title and link
    title_match = re.search(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
    snippet_match = re.search(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
    
    if title_match:
        link = title_match.group(1)
        if "/l/?uddg=" in link:
            from urllib.parse import unquote
            link_match = re.search(r'uddg=([^&]+)', link)
            if link_match:
                link = unquote(link_match.group(1))
        
        # Clean title HTML tags
        title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
        title = html.unescape(title)
        
        # Extract snippet
        snippet = ""
        if snippet_match:
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
            snippet = html.unescape(snippet)
            
        results.append({
            "title": title,
            "link": link,
            "snippet": snippet
        })

print(f"Extracted {len(results)} results:")
for i, res in enumerate(results[:5]):
    print(f"Result {i+1}:")
    print(f"  Title: {res['title']}")
    print(f"  Link:  {res['link']}")
    print(f"  Snippet: {res['snippet']}")
    print()
