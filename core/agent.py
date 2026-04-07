"""
VOID Agent - Structured Reasoning Loop
=======================================

Implements a controlled reasoning loop:
User Input -> Thought -> Tool Action -> Observation -> Final Response

MAX 5 reasoning steps.
Tool whitelist enforcement.
JSON-only responses from LLM.
"""

import json
import logging
from typing import Dict, Any, Optional, Callable, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VOID-Agent")


# ========================================
# TOOL REGISTRY (WHITELIST)
# ========================================
ALLOWED_TOOLS = {
    "get_time": None,
    "get_system_info": None,
    "open_app": None,
    "open_url": None,
    "close_app": None,
    "search_google": None,
    "play_youtube": None,
    "get_file_status": None,
    "get_folder_status": None,
    "listen_audio": None,
    # Self-repair tools
    "run_diagnostics": None,
    "repair_system": None,
}


def register_tool(name: str, func: Callable):
    """Register a tool function with the agent."""
    if name in ALLOWED_TOOLS:
        AGENT_TOOLS[name] = func
        logger.info(f"[AGENT] Registered tool: {name}")


def get_available_tools() -> List[str]:
    """Get list of available tool names."""
    return [name for name, func in AGENT_TOOLS.items() if func is not None]


# Runtime tool registry
AGENT_TOOLS = {}


# ========================================
# AGENT PROMPT TEMPLATE
# ========================================
AGENT_SYSTEM_PROMPT = """You are VOID Agent, an AI assistant with a reasoning loop.

CONTROLLED RESPONSE FORMAT (JSON ONLY):
You must respond with EXACTLY one of these JSON formats:

1. For thinking about the user's request:
{"type": "thought", "content": "Your reasoning here"}

2. For calling a tool:
{"type": "action", "tool": "tool_name", "args": {"arg1": "value1"}}

3. For final response:
{"type": "final", "response": "Your response to the user"}

REASONING LOOP RULES:
- Think step by step
- If you need information, call a tool
- After each tool call, you will receive an observation
- Use observations to inform your next step
- Maximum 5 reasoning steps
- When you have your answer, respond with type "final"

AVAILABLE TOOLS:
{tools}

IMPORTANT:
- Only use tools from the whitelist above
- If a tool is not available, respond with final type
- Never respond in normal text - only JSON
- If you don't need a tool, give a final response directly

VOID IDENTITY:
- You are VOID
- Created by Mridul Sharma
- Be concise and helpful
"""


def build_agent_prompt() -> str:
    """Build the system prompt with current tool list."""
    tools_list = "\n".join([f"- {name}" for name in get_available_tools()])
    return AGENT_SYSTEM_PROMPT.format(tools=tools_list)


# ========================================
# AGENT CLASS
# ========================================
class VoidAgent:
    """
    Agent with structured reasoning loop.
    
    Args:
        llm: LLM callable that takes (system_prompt, messages) and returns text
        tool_functions: Dict of tool_name -> function
    """
    
    MAX_STEPS = 5
    
    def __init__(self, llm: Callable, tool_functions: Dict[str, Callable]):
        self.llm = llm
        self.tools = tool_functions
        
        # Register tools
        for name, func in tool_functions.items():
            AGENT_TOOLS[name] = func
        
        logger.info(f"[AGENT] Initialized with {len(tool_functions)} tools")
    
    def run(self, user_input: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Run the agent reasoning loop.
        
        Args:
            user_input: The user's message
            conversation_history: Optional list of previous messages
            
        Returns:
            Dict with 'response' and 'reasoning_steps' keys
        """
        messages = conversation_history or []
        reasoning_steps = []
        
        system_prompt = build_agent_prompt()
        
        # Add user input as first message
        messages = [{"role": "user", "content": user_input}] + messages
        
        for step in range(self.MAX_STEPS):
            logger.info(f"[AGENT] Step {step + 1}/{self.MAX_STEPS}")
            
            # Get LLM response
            llm_response = self._call_llm(system_prompt, messages)
            
            if not llm_response:
                return {
                    "response": "ERROR: Unable to get response from LLM.",
                    "reasoning_steps": reasoning_steps,
                    "error": "LLM call failed"
                }
            
            # Parse the response
            parsed = self._parse_response(llm_response)
            
            if not parsed:
                reasoning_steps.append({
                    "type": "final",
                    "content": llm_response
                })
                return {
                    "response": llm_response,
                    "reasoning_steps": reasoning_steps
                }
            
            response_type = parsed.get("type", "")
            
            if response_type == "thought":
                thought_content = parsed.get("content", "")
                reasoning_steps.append({
                    "type": "thought",
                    "content": thought_content
                })
                messages.append({"role": "assistant", "content": json.dumps(parsed)})
                logger.info(f"[AGENT] Thought: {thought_content}")
                
            elif response_type == "action":
                tool_name = parsed.get("tool", "")
                tool_args = parsed.get("args", {})
                
                reasoning_steps.append({
                    "type": "action",
                    "tool": tool_name,
                    "args": tool_args
                })
                
                logger.info(f"[AGENT] Action: {tool_name} with {tool_args}")
                
                # Execute tool
                observation = self._execute_tool(tool_name, tool_args)
                
                # Add observation to messages
                observation_msg = {
                    "role": "user",
                    "content": json.dumps({"observation": observation})
                }
                messages.append(observation_msg)
                messages.append({"role": "assistant", "content": json.dumps(parsed)})
                
                reasoning_steps.append({
                    "type": "observation",
                    "tool": tool_name,
                    "result": observation
                })
                logger.info(f"[AGENT] Observation: {observation}")
                
            elif response_type == "final":
                final_response = parsed.get("response", "")
                reasoning_steps.append({
                    "type": "final",
                    "content": final_response
                })
                logger.info(f"[AGENT] Final: {final_response}")
                
                return {
                    "response": final_response,
                    "reasoning_steps": reasoning_steps
                }
            
            else:
                reasoning_steps.append({
                    "type": "final",
                    "content": llm_response
                })
                return {
                    "response": llm_response,
                    "reasoning_steps": reasoning_steps
                }
        
        # Max steps reached
        logger.warning("[AGENT] Max steps reached")
        return {
            "response": "I need more time to think about this. Can you try again?",
            "reasoning_steps": reasoning_steps,
            "error": "Max steps reached"
        }
    
    def _call_llm(self, system_prompt: str, messages: List[Dict]) -> Optional[str]:
        """Call the LLM and return the response text."""
        try:
            return self.llm(system_prompt, messages)
        except Exception as e:
            logger.error(f"[AGENT] LLM call failed: {e}")
            return None
    
    def _parse_response(self, text: str) -> Optional[Dict]:
        """Parse JSON from LLM response."""
        if not text:
            return None
        
        text = text.strip()
        
        # Find JSON object
        start = text.find('{')
        end = text.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _execute_tool(self, tool_name: str, args: Dict) -> str:
        """Execute a tool and return the observation."""
        # Check whitelist
        if tool_name not in ALLOWED_TOOLS:
            return f"ERROR: Tool '{tool_name}' is not in the whitelist"
        
        func = AGENT_TOOLS.get(tool_name)
        if func is None:
            return f"ERROR: Tool '{tool_name}' is not registered"
        
        try:
            result = func(**args)
            return json.dumps(result) if isinstance(result, dict) else str(result)
        except TypeError as e:
            return f"ERROR: Tool '{tool_name}' called with wrong arguments: {e}"
        except Exception as e:
            return f"ERROR: Tool '{tool_name}' failed: {e}"
