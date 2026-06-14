import asyncio
import json
import logging
import os
import requests
from typing import Any, AsyncGenerator, Dict, List, Optional
from backend.providers.base import BaseProvider

logger = logging.getLogger("void.providers.kimi")

class KimiProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "kimi-k2.7-code", base_url: str = "https://api.moonshot.cn/v1"):
        self.api_key = api_key or os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout = 60.0

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("Kimi/Moonshot API key not provided or configured. Please set it in Settings.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            url = f"{self.base_url}/models"
            resp = await asyncio.to_thread(requests.get, url, headers=self._get_headers(), timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.3
        }

        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            ))
            resp.raise_for_status()
            result_json = resp.json()
            return result_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[Kimi] Chat failed: {e}", exc_info=True)
            raise e

    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.3
        }

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

            async for line in read_lines_generator():
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data:"):
                    data_body = line_str[5:].strip()
                    if data_body == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_body)
                        token = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if token:
                            yield token
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[Kimi] Chat stream failed: {e}", exc_info=True)
            raise e

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.3
        }
        
        timeout_val = timeout if timeout is not None else self.timeout
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout_val)
            resp.raise_for_status()
            result_json = resp.json()
            return result_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[Kimi] Generate failed: {e}", exc_info=True)
            raise e
