import json
import sys
import io

# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def print_last_response(path):
    print(f"\n==================== Last response of {path.split('/')[-3]} ====================")
    last_resp = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                if data.get("type") == "PLANNER_RESPONSE" and data.get("content"):
                    last_resp = data.get("content")
        if last_resp:
            print(last_resp.strip()[:2000]) # Limit length
            if len(last_resp) > 2000:
                print("\n[TRUNCATED...]")
        else:
            print("No response found.")
    except Exception as e:
        print("Error reading path:", e)

if __name__ == "__main__":
    subagents = [
        "3188de01-b754-4c8b-a822-78a9c703d3b8", # Voice
        "ce68cade-5eb9-43b6-9ed7-18f038d8866c", # Electron Startup
        "6202f0b3-d7d6-4fff-9e4c-bdfb162fa10a", # Backend Routes
        "728ec79c-9fbf-41c7-8370-1785b68fa591"  # Frontend UI
    ]
    for sa in subagents:
        path = f"C:/Users/HP/.gemini/antigravity/brain/{sa}/.system_generated/logs/transcript.jsonl"
        print_last_response(path)
