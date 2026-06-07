import json

transcript_path = r"C:\Users\HP\.gemini\antigravity\brain\99f8648c-3ff7-4a2e-b3a2-5b8ecee4c855\.system_generated\logs\transcript.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            step_index = data.get("step_index")
            msg_type = data.get("type")
            content = data.get("content", "")
            
            is_relevant = False
            if "whatsapp" in str(data).lower() or "unread" in str(data).lower():
                is_relevant = True
                
            if not is_relevant:
                continue
                
            # Print user inputs
            if msg_type == "USER_INPUT":
                print(f"\n[Step {step_index}] USER INPUT: {content.strip()}")
            
            # Print tool calls
            tool_calls = data.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    name = tc.get("name")
                    args = tc.get("args")
                    # filter out less interesting tools to save space
                    if any(w in str(tc).lower() for w in ["whatsapp", "unread", "message", "send"]):
                        print(f"  -> Step {step_index} Tool Call: {name} with {args}")
                        
        except Exception as e:
            pass
