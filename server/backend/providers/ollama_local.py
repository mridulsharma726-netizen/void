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
        self.timeout = 120
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

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.model_detected:
            self._detect_model()
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        options = self._get_dynamic_options(prompt)
        
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
            return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[Ollama] Chat failed: {e}", exc_info=True)
            raise e

    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        if not self.model_detected:
            self._detect_model()
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        options = self._get_dynamic_options(prompt)
        
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
        except Exception as e:
            logger.error(f"[Ollama] Chat stream failed: {e}", exc_info=True)
            raise e

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        if not self.model_detected:
            self._detect_model()
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
        except Exception as e:
            logger.error(f"[Ollama] Generate failed: {e}", exc_info=True)
            raise e
