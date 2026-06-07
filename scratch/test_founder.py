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
    
    print("--- 1. Testing skipit_assistant (bookings_today) ---")
    res1 = await manager.execute("skipit_assistant", {"sub_action": "bookings_today"})
    print(f"Status: {res1.meta.get('status')}")
    print(f"Output:\n{res1.output}\n")
    
    print("--- 2. Testing skipit_assistant (inactive_listings) ---")
    res2 = await manager.execute("skipit_assistant", {"sub_action": "inactive_listings"})
    print(f"Status: {res2.meta.get('status')}")
    print(f"Output:\n{res2.output}\n")
    
    print("--- 3. Testing skipit_assistant (inactive_users) ---")
    res3 = await manager.execute("skipit_assistant", {"sub_action": "inactive_users", "days": 60})
    print(f"Status: {res3.meta.get('status')}")
    print(f"Output:\n{res3.output}\n")
    
    print("--- 4. Testing skipit_assistant (weekly_report) ---")
    res4 = await manager.execute("skipit_assistant", {"sub_action": "weekly_report"})
    print(f"Status: {res4.meta.get('status')}")
    print(f"Output:\n{res4.output}\n")
    
    print("--- 5. Testing smart_cart_assistant (pilot_performance) ---")
    res5 = await manager.execute("smart_cart_assistant", {"sub_action": "pilot_performance"})
    print(f"Status: {res5.meta.get('status')}")
    print(f"Output:\n{res5.output}\n")
    
    print("--- 6. Testing smart_cart_assistant (revenue_projections) ---")
    res6 = await manager.execute("smart_cart_assistant", {"sub_action": "revenue_projections"})
    print(f"Status: {res6.meta.get('status')}")
    print(f"Output:\n{res6.output}\n")
    
    print("--- 7. Testing smart_cart_assistant (store_pitch_deck) ---")
    res7 = await manager.execute("smart_cart_assistant", {"sub_action": "store_pitch_deck"})
    print(f"Status: {res7.meta.get('status')}")
    print(f"Output:\n{res7.output}\n")
    
    print("--- 8. Testing business_intelligence ---")
    res8 = await manager.execute("business_intelligence", {})
    print(f"Status: {res8.meta.get('status')}")
    print(f"Output:\n{res8.output}\n")

if __name__ == "__main__":
    asyncio.run(main())
