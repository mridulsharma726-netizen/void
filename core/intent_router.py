import json
from core.brain import ask_llm

def detect_intent_and_params(command: str) -> dict:
    """Use LLM to detect intent and parameters from command."""
    prompt = f"""
Analyze the following user command and determine the intent and any parameters.
Intents: system_info, time, open_app, open_url, search_web, workflow, chat.

For open_app: parameters {{ "app_name": "name" }}
For open_url: parameters {{ "url": "url" }}
For search_web: parameters {{ "query": "query" }}
For workflow: parameters {{ "steps": ["step1", "step2"] }} if it's a sequence like "open chrome then search cats"
For system_info or time: parameters {{}}
For chat: parameters {{}}

Return only JSON: {{"intent": "intent_name", "parameters": {{...}}}}
Command: {command}
"""
    response = ask_llm(prompt)
    try:
        # Extract JSON from response
        start = response.find('{')
        end = response.rfind('}') + 1
        json_str = response[start:end]
        data = json.loads(json_str)
        return data
    except:
        return {"intent": "chat", "parameters": {}}
