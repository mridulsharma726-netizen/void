import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from server.backend.intent_router import IntentRouter

async def main():
    router = IntentRouter()
    queries = [
        "create a presentation about Smart Cart",
        "summarize today's inbox",
        "reply to important emails",
        "reply to mail_101 saying I am interested in Thursday",
        "plan my week",
        "schedule coding time every morning at 9am"
    ]
    for q in queries:
        res = await router.classify(q)
        print(f"Query: {q}")
        print(f"  -> Intent: {res.intent}, Action: {res.action}, Params: {res.params}\n")

if __name__ == "__main__":
    asyncio.run(main())
