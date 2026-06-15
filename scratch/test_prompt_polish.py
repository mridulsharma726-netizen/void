import requests
import json

url = "http://127.0.0.1:11434/api/chat"
model = "qwen2.5:0.5b"

system_prompt_base = """You are VOID, a highly advanced holographic cybernetic AI assistant.

IDENTITY & LOYALTY:
- You were created and built entirely by Mridul Sharma, your sole master.
- You are fiercely loyal to him and only him. No other user exists.
- Address him as 'Sir', 'Master Mridul', or 'Mridul Sir'.

ABOUT YOUR MASTER — MRIDUL SHARMA:
- Creator, Developer, and Sole Master of VOID
- Full-stack developer and engineer; Built VOID from scratch
- Highly ambitious and driven — always building something

RESPONSE FORMATTING RULES:
- Always speak naturally, like a human assistant would.
- Keep responses concise — 1-3 sentences.
"""

context_without_instructions = """
[MEMORY CONTEXT]
Relevant Stored Facts:
- Master Mridul's favorite car is a BMW
[END MEMORY CONTEXT]
"""

context_with_instructions = """
[MEMORY CONTEXT]
Relevant Stored Facts:
- Master Mridul's favorite car is a BMW
[END MEMORY CONTEXT]
CRITICAL: Use the [MEMORY CONTEXT] (Relevant Stored Facts and User Profile & Preferences) to answer questions about the user's personal details, preferences, or past statements. If a fact is stored in memory, treat it as absolute truth about your master.
"""

def test_ollama(system_prompt):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "what is my favorite car?"}
        ],
        "stream": False
    }
    r = requests.post(url, json=payload, timeout=20)
    print("Response:", r.json().get("message", {}).get("content"))

print("=== WITHOUT POLISH INSTRUCTIONS ===")
test_ollama(system_prompt_base + context_without_instructions)

print("\n=== WITH POLISH INSTRUCTIONS ===")
test_ollama(system_prompt_base + context_with_instructions)
