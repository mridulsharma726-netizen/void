import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from backend.schemas import IntentResult, PipelineResponse, ToolCall
from backend.llm_client import OllamaClient  
from backend.memory_manager import MemoryManager
from backend.tool_manager import ToolManager
from backend.validator import ResponseValidator
from backend.repair_system import RepairSystem

logger = logging.getLogger("void.decision")

class DecisionEngine:
    """Central orchestrator: intent → decision → execution → validation."""
    
    def __init__(
        self,
        router,
        llm: OllamaClient,
        memory: MemoryManager,
        tool_manager: ToolManager,
        validator: ResponseValidator,
        repair_engine: Optional[RepairSystem] = None
    ):
        self.router = router
        self.llm = llm
        self.memory = memory
        self.tool_manager = tool_manager
        self.validator = validator
        self.repair_engine = repair_engine
        self.llm_fallback_enabled = True  # Configurable

    async def run(self, user_text: str) -> PipelineResponse:
        """Structured local agent orchestration loop."""
        started = time.perf_counter()
        
        # 1. Pre-validation & Input Sanitization
        text = (user_text or "").strip()
        if not text:
            return self._validated_response("Please say something.", "empty_input")
        
        # 2. Intent Routing
        intent = await self.router.classify(text)
        self.memory.remember_turn("user", text)
        logger.info(f"[ORCHESTRATOR] Routed Intent: {intent.intent}:{intent.action}")
        
        # 3. Memory Extraction / Reflection
        try:
            from backend.memory_manager import extract_and_remember
            extracted = extract_and_remember(text)
            if extracted:
                logger.info(f"[ORCHESTRATOR] Memory extracted: {extracted}")
                self.memory.add_fact(extracted)
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")

        # 4. Decision & Execution
        reply = ""
        try:
            if intent.intent == "system":
                # System execution
                logger.info(f"[ORCHESTRATOR] Executing System Command: {intent.action}")
                reply = await self._handle_system(intent.action, text)
            elif intent.intent == "command":
                # Planner / Tool execution with verification
                logger.info(f"[ORCHESTRATOR] Executing Action: {intent.action} with params={intent.params}")
                tool_result = await self._handle_tool(intent.action, intent.params)
                
                # 5. Output Verification
                if tool_result.output and "error" not in tool_result.output.lower():
                    logger.info(f"[ORCHESTRATOR] Verification successful: {intent.action} executed.")
                    reply = tool_result.output
                else:
                    logger.warning(f"[ORCHESTRATOR] Action output failed verification, applying recovery.")
                    reply = f"The action '{intent.action}' was executed, but returned an observation: {tool_result.output or 'No output'}"
            else:
                # Chat logic with context assembly
                logger.info("[ORCHESTRATOR] Assembling context and generating LLM reply.")
                reply = await self._handle_chat(text)
                
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Loop execution failed: {e}", exc_info=True)
            reply = "I encountered an error executing that request, Sir. Self-recovery initialized."
            if self.repair_engine:
                await self.repair_engine.auto_recover(f"decision_engine: {e}")
        
        # 6. Post-validation & Memory Reflection
        self.memory.remember_turn("assistant", reply)
        validated = self.validator.validate({"reply": reply, "meta": {
            "intent": intent.intent, 
            "action": intent.action,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "timestamp": time.time()
        }})
        
        # 7. Final Response Generation
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(f"[ORCHESTRATOR] Pipeline complete in {latency_ms}ms")
        
        return PipelineResponse(reply=validated["reply"], meta=validated["meta"])

    async def _handle_system(self, action: str, text: str) -> str:
        """System commands (memory, diagnostics, repair)."""
        if action == "clear_memory":
            self.memory.clear()
            return "🧹 Memory cleared."
        elif action == "show_memory":
            facts = self.memory.list_facts()[-10:]
            return "\n".join(f"• {f}" for f in facts) or "No facts stored."
        elif action == "repair":
            if self.repair_engine:
                report = await self.repair_engine.run()
                return f"🔧 Repair: {report.get('fixed_count', 0)} fixed."
            return "Repair unavailable."
        elif action == "diagnostics":
            report = await self._diagnostics()
            return f"Diagnostics: {report['status']} ({len(report['issues'])} issues)"
        elif text.lower().startswith("remember "):
            fact = text[9:].strip()
            self.memory.add_fact(fact)
            return "💾 Remembered."
        return "System command OK."

    async def _handle_tool(self, action: str, params: Dict[str, Any]) -> ToolCall:
        """Execute validated tool."""
        if action == "unknown_command":
            return ToolCall(
                name="unknown", input=params, 
                output="Command noted. Tool integration pending."
            )
        tool_result = await self.tool_manager.execute(action, params)
        return tool_result

    async def _handle_chat(self, text: str) -> str:
        """LLM chat with context."""
        if not await self.llm.available():
            return "🤖 Offline mode: LLM unavailable."
        
        context = self.memory.short_term[-8:]  # Reduced for speed
        facts = "; ".join(self.memory.list_facts()[-5:])
        if facts:
            context = [{"role": "system", "content": f"Facts: {facts}"}] + context
        
        return await self.llm.chat(context, text)

    async def _diagnostics(self) -> Dict[str, Any]:
        """Quick diagnostics."""
        # Delegate to tool manager + LLM
        tools_health = await self.tool_manager.check_all_tools()
        llm_health = await self.llm.available()
        return {
            "status": "healthy" if llm_health and tools_health["status"] == "OK" else "degraded",
            "tools_failed": tools_health["failed"],
            "llm_online": llm_health
        }

    def _validated_response(self, reply: str, intent: str) -> PipelineResponse:
        """Quick validated response."""
        validated = self.validator.validate({"reply": reply, "meta": {"intent": intent}})
        return PipelineResponse(reply=validated["reply"], meta=validated["meta"])
