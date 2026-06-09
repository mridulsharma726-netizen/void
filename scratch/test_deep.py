import asyncio
from backend.deep_research import ResearchManager

async def main():
    manager = ResearchManager()
    res = await manager.run_workflow("the internet find the tools that can do the task")
    print("DONE:", res)

if __name__ == "__main__":
    asyncio.run(main())
