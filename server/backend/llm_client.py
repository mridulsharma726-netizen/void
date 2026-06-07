import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List

import requests

logger = logging.getLogger("void.llm")

# Import the rich owner profile
try:
    from backend.owner_profile import get_owner_system_prompt
    _BASE_PROMPT = get_owner_system_prompt()
except ImportError:
    _BASE_PROMPT = "You are VOID, a highly advanced AI system. Your creator and master is Mridul Sharma. Keep responses concise."

# Append anti-raw-data instructions
SYSTEM_PROMPT = _BASE_PROMPT + """

RESPONSE FORMATTING RULES:
- NEVER output raw JSON, Python dicts, file paths, status codes, or technical error strings.
- NEVER say things like "{'status': 'ok'}" or "HTTP 500" or "Error: connection refused".
- Always speak naturally, like a human assistant would.
- If a tool/action succeeded, describe the outcome naturally (e.g., "Chrome is open now, Sir." not "✅ Opened 'chrome'").
- If a tool/action failed, explain what went wrong simply (e.g., "I couldn't open that app, Sir. It might not be installed." not "❌ Failed to open 'app': FileNotFoundError").
- Use markdown formatting when helpful: **bold** for emphasis, `code` for technical terms, bullet lists for multiple items.
- Keep responses concise — 1-3 sentences for simple things, more for complex explanations."""

class OllamaClient:
    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.chat_url = f"{base_url}/api/chat"
        self.tags_url = f"{base_url}/api/tags"
        self.timeout = 60  # Increase to 60s to allow model loading
        self.system_prompt = SYSTEM_PROMPT
        
        # Self-optimization: auto-detect lightweight models (once at init)
        try:
            resp = requests.get(self.tags_url, timeout=1.5)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                for fast_model in ["qwen2.5:0.5b", "qwen2.5:1.5b"]:
                    if fast_model in models or f"{fast_model}:latest" in models:
                        self.model = fast_model
                        logger.info(f"[LLM] Auto-selected fast model: {self.model}")
                        break
        except:
            pass

    async def available(self) -> bool:
        try:
            requests.get(self.tags_url, timeout=1.5)
            return True
        except:
            return False

    async def warmup(self) -> bool:
        try:
            await self.chat([], "ping")
            return True
        except:
            return False

    def _get_dynamic_options(self, user_text: str) -> Dict[str, Any]:
        """Analyzes prompt content to return optimal parameters for Ollama."""
        text_lower = user_text.lower()
        
        # Check for Creative Writing intent
        creative_keywords = [
            "write a story", "write a poem", "compose", "creative writing", "write a song", 
            "create a story", "tell a story", "fictional", "write an essay", "poetry",
            "screenplay", "script", "creative content"
        ]
        is_creative = any(kw in text_lower for kw in creative_keywords) or (
            "write" in text_lower and any(w in text_lower for w in ["story", "poem", "song", "script", "novel", "lyrics", "fiction"])
        )
        
        # Check for Logic Puzzle / Reasoning intent
        puzzle_keywords = [
            "puzzle", "riddle", "logic", "solve", "math", "reasoning", "step by step",
            "explain why", "prove", "algorithmic", "how to solve"
        ]
        is_puzzle = any(kw in text_lower for kw in puzzle_keywords)
        
        if is_creative:
            return {
                "temperature": 0.85,
                "num_predict": 1024,
                "num_ctx": 4096,
                "num_thread": 4
            }
        elif is_puzzle:
            return {
                "temperature": 0.15,
                "num_predict": 1024,
                "num_ctx": 4096,
                "num_thread": 4
            }
        else:
            return {
                "temperature": 0.5,
                "num_predict": 512,
                "num_ctx": 2048,
                "num_thread": 4
            }

    def build_context_prompt(self, user_text: str) -> str:
        """
        Builds the memory-enriched system prompt.
        Retrieves relevant semantic facts and gets overall memory context,
        then appends them to the system prompt.
        """
        try:
            from backend.memory_manager import query_semantic_facts, get_memory_context
            # Query relevant semantic facts
            relevant_facts = query_semantic_facts(user_text, limit=3)
            # Get user info and preferences
            pref_context = get_memory_context()
            
            memory_block = []
            if relevant_facts:
                memory_block.append("Relevant Stored Facts:\n" + "\n".join(f"- {fact}" for fact in relevant_facts))
            if pref_context and pref_context != "No stored memory yet.":
                memory_block.append(f"User Profile & Preferences:\n{pref_context}")
                
            if memory_block:
                enriched_context = "\n\n[MEMORY CONTEXT]\n" + "\n\n".join(memory_block) + "\n[END MEMORY CONTEXT]"
                return self.system_prompt + enriched_context
        except Exception as e:
            logger.error(f"Failed to build enriched context prompt: {e}")
        return self.system_prompt

    async def chat(self, history: List[Dict], user_text: str) -> str:
        # Extract and remember any new facts
        try:
            from backend.memory_manager import extract_and_remember
            extract_and_remember(user_text)
        except Exception as e:
            logger.error(f"Failed to extract and remember facts in chat: {e}")

        system_prompt = self.build_context_prompt(user_text)
        messages = [{"role": "system", "content": system_prompt}] + history[-5:] + [{"role": "user", "content": user_text}]
        options = self._get_dynamic_options(user_text)
        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                self.chat_url, 
                json={
                    "model": self.model, 
                    "messages": messages, 
                    "stream": False,
                    "options": options
                }, 
                timeout=self.timeout
            ))
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[LLM ERROR] Chat failed: {e}", exc_info=True)
            return "I'm having a brief connection issue, Sir. Give me a moment."

    async def summarize_tool_output(self, user_request: str, action_name: str, raw_output: str, is_success: bool = True) -> str:
        """Pass raw tool output through LLM to produce a natural, human-friendly response."""
        if not is_success:
            try:
                from tools.error_interpreter import interpret_error
                friendly_error = interpret_error(raw_output)
            except Exception:
                friendly_error = "An unexpected error occurred during execution."

            prompt = (
                f"The user asked: \"{user_request}\"\n"
                f"I executed the action '{action_name}' but it failed with this raw error: {raw_output}\n"
                f"Human-friendly explanation of the issue: {friendly_error}\n\n"
                f"Respond to the user with a respectful, concise explanation of the failure and what they can do next, "
                f"speaking in your premium cybernetic AI assistant persona (addressing them as Sir/Master Mridul). "
                f"Be direct, polite, and explain the next step. Do NOT include raw traceback text or JSON."
            )
        else:
            prompt = (
                f"The user asked: \"{user_request}\"\n"
                f"I executed the action '{action_name}' and got this raw result: {raw_output}\n\n"
                f"Respond naturally to the user about what happened. Be concise and conversational. "
                f"Do NOT include the raw output — describe the outcome in plain English, "
                f"speaking in your premium cybernetic AI assistant persona (addressing them as Sir/Master Mridul)."
            )
        return await self.chat([], prompt)

    async def chat_stream(self, history: List[Dict], user_text: str) -> AsyncGenerator[str, None]:
        # Extract and remember any new facts
        try:
            from backend.memory_manager import extract_and_remember
            extract_and_remember(user_text)
        except Exception as e:
            logger.error(f"Failed to extract and remember facts in chat_stream: {e}")

        system_prompt = self.build_context_prompt(user_text)
        messages = [{"role": "system", "content": system_prompt}] + history[-5:] + [{"role": "user", "content": user_text}]
        options = self._get_dynamic_options(user_text)
        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                self.chat_url, 
                json={
                    "model": self.model, 
                    "messages": messages, 
                    "stream": True,
                    "options": options
                }, 
                stream=True, 
                timeout=self.timeout
            ))
            
            def read_lines():
                return list(resp.iter_lines())
                
            lines = await asyncio.to_thread(read_lines)
            for line in lines:
                if line:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
        except Exception as e:
            logger.error(f"[LLM ERROR] Chat stream failed: {e}", exc_info=True)
            yield "Stream interrupted. Please try again, Sir."

