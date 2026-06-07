import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from server.backend.tool_manager import ToolManager
from server.backend.tools_runtime import ToolRuntime

async def main():
    runtime = ToolRuntime()
    manager = ToolManager(runtime)
    
    print("--- 1. Testing create_presentation ---")
    res1 = await manager.execute("create_presentation", {"topic": "Smart Cart"})
    print(f"Status: {res1.meta.get('status')}")
    print(f"Output:\n{res1.output}\n")
    
    print("--- 2. Testing manage_email (summarize) ---")
    res2 = await manager.execute("manage_email", {"sub_action": "summarize"})
    print(f"Status: {res2.meta.get('status')}")
    print(f"Output:\n{res2.output}\n")
    
    print("--- 3. Testing manage_email (draft reply) ---")
    res3 = await manager.execute("manage_email", {
        "sub_action": "draft",
        "email_id": "mail_101",
        "instructions": "I am interested in Thursday call"
    })
    print(f"Status: {res3.meta.get('status')}")
    print(f"Output:\n{res3.output}\n")
    
    print("--- 4. Testing manage_calendar (plan_week) ---")
    res4 = await manager.execute("manage_calendar", {"sub_action": "plan_week"})
    print(f"Status: {res4.meta.get('status')}")
    print(f"Output:\n{res4.output}\n")
    
    print("--- 5. Testing manage_calendar (schedule_event via NLP) ---")
    res5 = await manager.execute("manage_calendar", {
        "sub_action": "schedule_event",
        "raw_text": "schedule a meeting with suppliers on Friday at 2:00 PM high priority"
    })
    print(f"Status: {res5.meta.get('status')}")
    print(f"Output:\n{res5.output}\n")

if __name__ == "__main__":
    asyncio.run(main())
