import json
import sys

transcript_path = r"C:\Users\HP\.gemini\antigravity\brain\3188de01-b754-4c8b-a822-78a9c703d3b8\.system_generated\logs\transcript.jsonl"
if len(sys.argv) > 1:
    transcript_path = sys.argv[1]

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            step_index = data.get("step_index")
            msg_type = data.get("type")
            content = data.get("content", "")
            
            # Print user inputs
            if msg_type == "USER_INPUT":
                print(f"\n[Step {step_index}] USER INPUT: {content.strip()}")
            elif msg_type == "PLANNER_RESPONSE":
                print(f"\n[Step {step_index}] PLANNER_RESPONSE:\n{content.strip()}")
            elif msg_type == "SYSTEM" and "finished" in str(content).lower():
                print(f"\n[Step {step_index}] SYSTEM: {content}")
        except Exception as e:
            pass

