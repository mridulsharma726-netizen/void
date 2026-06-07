"""Thin wrapper delegating to DecisionEngine."""
import logging
from typing import Optional

from backend.decision_engine import DecisionEngine
from backend.diagnostics import DiagnosticsEngine
from backend.llm_client import OllamaClient
from backend.memory_manager import MemoryManager
from backend.repair_system import RepairSystem
from backend.schemas import PipelineResponse
from backend.tool_manager import ToolManager
from backend.validator import ResponseValidator

logger = logging.getLogger("void.pipeline")

class ChatPipeline:
    """Legacy compatibility → delegates to DecisionEngine."""
    
    def __init__(
        self,
        router,  # Unused now
        memory: MemoryManager,
        llm: OllamaClient,
        tool_manager: ToolManager,
        validator: ResponseValidator,
        diagnostics: Optional[DiagnosticsEngine] = None,
        repair_engine: Optional[RepairSystem] = None,
    ):
        # Create DecisionEngine internally
        self.engine = DecisionEngine(
            router=router,  # Still passed for compatibility
            llm=llm,
            memory=memory,
            tool_manager=tool_manager,
            validator=validator,
            repair_engine=repair_engine
        )
        logger.info("ChatPipeline → DecisionEngine initialized")

    async def run(self, user_text: str) -> PipelineResponse:
        """Delegate to engine."""
        logger.debug(f"Pipeline delegating: '{user_text[:30]}...'")
        return await self.engine.run(user_text)
