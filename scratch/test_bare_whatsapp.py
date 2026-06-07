import sys
import asyncio
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "server"))

from backend.intent_router import IntentRouter
from backend.tool_schemas import SendWhatsAppInput

async def test_bare_whatsapp():
    router = IntentRouter(use_llm_fallback=False)
    
    test_queries = [
        "send whatsapp message",
        "send whatsapp",
        "whatsapp",
        "send whatsapp message to Papa saying hello",
        "send whatsapp to krish hii",
        "whatsapp krish hii",
        "send krish saying hii",
    ]
    
    print("=== TESTING BARE WHATSAPP ROUTING ===")
    for q in test_queries:
        res = await router.classify(q)
        print(f"Query: '{q}' -> Intent: {res.intent}, Action: {res.action}, Params: {res.params}")
        
        if res.intent == "command" and res.action == "send_whatsapp":
            # Test schema validation
            try:
                validated = SendWhatsAppInput(**res.params)
                print(f"  [VALIDATION OK] contact='{validated.contact}', message='{validated.message}'")
            except Exception as e:
                print(f"  [VALIDATION FAIL] {e}")

if __name__ == "__main__":
    asyncio.run(test_bare_whatsapp())
