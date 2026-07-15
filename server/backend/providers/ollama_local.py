import asyncio
import json
import logging
import requests
from typing import Any, AsyncGenerator, Dict, List, Optional
from backend.providers.base import BaseProvider

logger = logging.getLogger("void.providers.ollama")

class OllamaProvider(BaseProvider):
    def __init__(self, model: str = "qwen2.5:0.5b", base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.base_url = base_url
        self.chat_url = f"{base_url}/api/chat"
        self.tags_url = f"{base_url}/api/tags"
        self.timeout = 600
        self.model_detected = False
        self._detect_model()

    def _detect_model(self):
        try:
            resp = requests.get(self.tags_url, timeout=5.0)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if self.model not in models and f"{self.model}:latest" not in models:
                    for fast_model in ["qwen2.5:0.5b", "qwen2.5:1.5b", "llama3.2:3b", "mistral"]:
                        if fast_model in models or f"{fast_model}:latest" in models:
                            self.model = fast_model
                            logger.info(f"[Ollama] Auto-selected fast model: {self.model}")
                            break
                self.model_detected = True
        except Exception as e:
            logger.debug(f"[Ollama] Model detection failed: {e}")

    def _get_dynamic_options(self, user_text: str) -> Dict[str, Any]:
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
                "temperature": 0.7,
                "num_predict": 512,
                "num_ctx": 4096,
                "num_thread": 4
            }

    async def available(self) -> bool:
        try:
            resp = await asyncio.to_thread(requests.get, self.tags_url, timeout=2.0)
            return resp.status_code == 200
        except:
            return False

    def _truncate_to_context_limit(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str], num_ctx: int) -> tuple[List[Dict[str, str]], str]:
        # Leave 512 tokens for output generation
        max_tokens = num_ctx - 512
        if max_tokens < 512:
            max_tokens = 512
            
        def est_tokens(text: str) -> int:
            return len(text) // 4
            
        sys_tokens = est_tokens(system_prompt) if system_prompt else 0
        prompt_tokens = est_tokens(prompt)
        
        # If the latest user prompt alone exceeds max_tokens, truncate it
        if prompt_tokens > max_tokens - 100:
            allowed_chars = (max_tokens - 100) * 4
            prompt = prompt[:allowed_chars] + "\n\n[Prompt truncated to fit context limits, Sir...]"
            prompt_tokens = est_tokens(prompt)
            
        pruned_history = list(history)
        while pruned_history and (sys_tokens + prompt_tokens + sum(est_tokens(m["content"]) for m in pruned_history) > max_tokens):
            pruned_history.pop(0)
            
        return pruned_history, prompt

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.model_detected:
            self._detect_model()
            
        options = self._get_dynamic_options(prompt)
        num_ctx = options.get("num_ctx", 4096)
        
        history, prompt = self._truncate_to_context_limit(history, prompt, system_prompt, num_ctx)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                self.chat_url, 
                json={
                    "model": self.model, 
                    "messages": messages, 
                    "stream": False,
                    "options": options
                }, 
                timeout=(5.0, self.timeout - 15)
            ))
            resp.raise_for_status()
            
            # Prometheus instrumentation
            try:
                from core.observability.telemetry import OLLAMA_CALLS
                OLLAMA_CALLS.labels(model=self.model, status="success").inc()
            except Exception:
                pass
                
            return resp.json().get("message", {}).get("content", "").strip()
        except requests.exceptions.Timeout as te:
            logger.error(f"[Ollama] Chat timed out: {te}")
            try:
                from core.observability.telemetry import OLLAMA_CALLS
                OLLAMA_CALLS.labels(model=self.model, status="timeout").inc()
            except Exception:
                pass
            raise asyncio.TimeoutError("The local AI model timed out. The request may be too complex, Sir.")
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"[Ollama] Connection failed. Service may be down: {ce}")
            try:
                from core.observability.telemetry import OLLAMA_CALLS
                OLLAMA_CALLS.labels(model=self.model, status="connection_error").inc()
            except Exception:
                pass
            raise RuntimeError("The local AI service (Ollama) is currently unreachable. Please make sure it is running, Sir.")
        except Exception as e:
            logger.error(f"[Ollama] Chat failed: {e}", exc_info=True)
            try:
                from core.observability.telemetry import OLLAMA_CALLS
                OLLAMA_CALLS.labels(model=self.model, status="error").inc()
            except Exception:
                pass
            raise RuntimeError(f"The local AI service encountered an error, Sir. Details: {str(e)}")


    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        if not self.model_detected:
            self._detect_model()
            
        options = self._get_dynamic_options(prompt)
        num_ctx = options.get("num_ctx", 4096)
        
        history, prompt = self._truncate_to_context_limit(history, prompt, system_prompt, num_ctx)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
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
                timeout=(5.0, self.timeout - 15)
            ))
            resp.raise_for_status()
            
            async def read_lines_generator():
                for line in resp.iter_lines():
                    if line:
                        yield line
                        
            async for line in read_lines_generator():
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
        except requests.exceptions.Timeout as te:
            logger.error(f"[Ollama] Chat stream timed out: {te}")
            yield "⚠️ [Timeout Error: The local AI model timed out, Sir.]"
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"[Ollama] Chat stream connection failed: {ce}")
            yield "⚠️ [Connection Error: The local AI service (Ollama) is currently unreachable, Sir.]"
        except Exception as e:
            logger.error(f"[Ollama] Chat stream failed: {e}", exc_info=True)
            yield f"⚠️ [Error: The local AI service encountered an issue, Sir. Details: {str(e)}]"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        if not self.model_detected:
            self._detect_model()
            
        num_ctx = 4096
        max_tokens = num_ctx - 512
        if len(prompt) // 4 > max_tokens:
            prompt = prompt[:max_tokens * 4] + "\n\n[Prompt truncated to fit context limits, Sir...]"
            
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format:
            payload["format"] = format
            
        url = self.chat_url.replace("/chat", "/generate")
        timeout_val = timeout if timeout is not None else self.timeout
        try:
            resp = requests.post(url, json=payload, timeout=timeout_val)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.Timeout as te:
            logger.error(f"[Ollama] Generate timed out: {te}")
            raise asyncio.TimeoutError("The local AI model timed out. The request may be too complex, Sir.")
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"[Ollama] Connection failed: {ce}")
            raise RuntimeError("The local AI service (Ollama) is currently unreachable. Please make sure it is running, Sir.")
        except Exception as e:
            logger.error(f"[Ollama] Generate failed: {e}", exc_info=True)
            raise RuntimeError(f"The local AI service encountered an error: {str(e)}")

    def discover_and_categorize_models(self) -> Dict[str, List[str]]:
        """Query Ollama /api/tags and dynamically group models into capability categories."""
        categories = {
            "Coding": [],
            "Reasoning": [],
            "Planning": [],
            "Vision": [],
            "Chat": [],
            "Lightweight": [],
            "Large": []
        }
        try:
            resp = requests.get(self.tags_url, timeout=5.0)
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                for m in models_data:
                    name = m.get("name", "")
                    details = m.get("details", {})
                    size_bytes = m.get("size", 0)
                    family = details.get("family", "").lower()
                    
                    is_coding = any(k in name.lower() for k in ["code", "coder", "starcoder", "deepseek-coder"]) or family == "starcoder"
                    is_reasoning = any(k in name.lower() for k in ["r1", "reason", "phi4", "qwq"])
                    is_vision = any(k in name.lower() for k in ["vision", "llava", "bakllava", "minicpm-v", "mllama"])
                    
                    is_lightweight = size_bytes < 2500000000 or any(k in name.lower() for k in ["0.5b", "1b", "1.5b", "3b", "3.2b"])
                    is_large = size_bytes > 8000000000 or any(k in name.lower() for k in ["13b", "14b", "32b", "70b"])

                    if is_coding:
                        categories["Coding"].append(name)
                    if is_reasoning:
                        categories["Reasoning"].append(name)
                        categories["Planning"].append(name)
                    if is_vision:
                        categories["Vision"].append(name)
                    if is_lightweight:
                        categories["Lightweight"].append(name)
                    elif is_large:
                        categories["Large"].append(name)
                    
                    categories["Chat"].append(name)
            
            # Fallback if no models in categories
            for cat, list_models in categories.items():
                if not list_models:
                    all_names = [m.get("name") for m in models_data]
                    categories[cat] = all_names
        except Exception as e:
            logger.error(f"[Ollama] Model discovery failed: {e}")
            
        return categories

