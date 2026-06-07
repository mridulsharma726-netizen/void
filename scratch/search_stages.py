import json
import os

path = r"C:\Users\HP\.gemini\antigravity\brain\dbee5573-f25d-4635-bb97-12af68a670d9\.system_generated\logs\transcript.jsonl"
if os.path.exists(path):
    print("Found transcript log!")
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if "stage" in line.lower():
                try:
                    obj = json.loads(line)
                    content = obj.get("content", "")
                    if any(term in content.lower() for term in ["stage 5", "stage5", "milestone 5"]):
                        print(f"--- Step {i} ---")
                        print(content)
                        print("\n" + "="*50 + "\n")
                except Exception as e:
                    pass
else:
    print("Log not found at:", path)
