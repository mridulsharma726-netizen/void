import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def extract_report(sa_id, sa_name):
    path = f"C:/Users/HP/.gemini/antigravity/brain/{sa_id}/.system_generated/logs/transcript.jsonl"
    print(f"\n==================== {sa_name} ({sa_id}) Report ====================")
    try:
        reports = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                # Look for tool calls to send_message or final PLANNER_RESPONSE
                tool_calls = data.get("tool_calls", [])
                for tc in tool_calls:
                    if tc.get("name") == "send_message":
                        msg = tc.get("args", {}).get("Message")
                        if msg:
                            reports.append(("send_message", msg))
                if data.get("type") == "PLANNER_RESPONSE" and data.get("content"):
                    content = data.get("content")
                    if "audit" in content.lower() or "report" in content.lower() or "comprehensive" in content.lower():
                        reports.append(("planner_response", content))
        if reports:
            # Print the last found report
            source, text = reports[-1]
            print(f"Source: {source}\n")
            print(text.strip())
        else:
            # Print the last few planner responses
            print("No explicit report found. Printing last 3 planner responses:")
            resps = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("type") == "PLANNER_RESPONSE" and data.get("content"):
                        resps.append(data.get("content"))
            for r in resps[-3:]:
                print("---")
                print(r.strip()[:500])
    except Exception as e:
        print("Error reading subagent:", e)

if __name__ == "__main__":
    subagents = {
        "3188de01-b754-4c8b-a822-78a9c703d3b8": "Voice System Auditor",
        "ce68cade-5eb9-43b6-9ed7-18f038d8866c": "Electron Startup Auditor",
        "6202f0b3-d7d6-4fff-9e4c-bdfb162fa10a": "Backend Routes Auditor",
        "728ec79c-9fbf-41c7-8370-1785b68fa591": "Frontend UI Auditor"
    }
    for sa_id, name in subagents.items():
        extract_report(sa_id, name)
