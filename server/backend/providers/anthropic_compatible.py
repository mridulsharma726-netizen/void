import asyncio
import json
import logging
import requests
from typing import Any, AsyncGenerator, Dict, List, Optional
from backend.providers.base import BaseProvider

logger = logging.getLogger("void.providers.anthropic_compatible")

class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022", base_url: str = "https://api.anthropic.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.timeout = 60.0

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("Anthropic API Key is missing.")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    async def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            # We check if we can send a minimal query to verify the key
            url = f"{self.base_url}/messages"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            resp = await asyncio.to_thread(lambda: requests.post(
                url, json=payload, headers=self._get_headers(), timeout=5.0
            ))
            return resp.status_code == 200 or resp.status_code == 400 # 400 means invalid request body but API key is authorized
        except Exception:
            return False

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({
                "role": role,
                "content": turn.get("content", "")
            })
        messages.append({
            "role": "user",
            "content": prompt
        })

        url = f"{self.base_url}/messages"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            ))
            resp.raise_for_status()
            result_json = resp.json()
            return result_json["content"][0]["text"].strip()
        except Exception as e:
            logger.error(f"[Anthropic] Chat failed: {e}", exc_info=True)
            raise e

    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        messages = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({
                "role": role,
                "content": turn.get("content", "")
            })
        messages.append({
            "role": "user",
            "content": prompt
        })

        url = f"{self.base_url}/messages"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3,
            "stream": True
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                stream=True,
                timeout=self.timeout
            ))
            resp.raise_for_status()

            async def read_lines_generator():
                for line in resp.iter_lines():
                    if line:
                        yield line

            current_event = None
            async for line in read_lines_generator():
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("event:"):
                    current_event = line_str[6:].strip()
                elif line_str.startswith("data:"):
                    data_body = line_str[5:].strip()
                    if current_event == "content_block_delta":
                        try:
                            chunk_data = json.loads(data_body)
                            token = chunk_data.get("delta", {}).get("text", "")
                            if token:
                                yield token
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"[Anthropic] Chat stream failed: {e}", exc_info=True)
            raise e

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        url = f"{self.base_url}/messages"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.3
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        timeout_val = timeout if timeout is not None else self.timeout
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout_val)
            resp.raise_for_status()
            result_json = resp.json()
            return result_json["content"][0]["text"].strip()
        except Exception as e:
            logger.error(f"[Anthropic] Generate failed: {e}", exc_info=True)
            raise e
