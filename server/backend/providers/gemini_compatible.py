import asyncio
import json
import logging
import requests
from typing import Any, AsyncGenerator, Dict, List, Optional
from backend.providers.base import BaseProvider

logger = logging.getLogger("void.providers.gemini_compatible")

class GeminiProvider(BaseProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash", base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.timeout = 60.0

    def _convert_history(self, history: List[Dict[str, str]], prompt: str) -> List[Dict[str, Any]]:
        contents = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": turn.get("content", "")}]
            })
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        return contents

    async def available(self) -> bool:
        if not self.api_key:
            return False
        try:
            # Simple metadata query to verify API key validity
            url = f"{self.base_url}/models?key={self.api_key}"
            resp = await asyncio.to_thread(requests.get, url, timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        contents = self._convert_history(history, prompt)
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            ))
            resp.raise_for_status()
            result_json = resp.json()
            # Extract content text
            return result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.error(f"[Gemini] Chat failed: {e}", exc_info=True)
            raise e

    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        contents = self._convert_history(history, prompt)
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
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
                    try:
                        chunk_data = json.loads(data_body)
                        token = chunk_data["candidates"][0]["content"]["parts"][0]["text"]
                        if token:
                            yield token
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[Gemini] Chat stream failed: {e}", exc_info=True)
            raise e

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
        if format == "json":
            payload["generationConfig"]["responseMimeType"] = "application/json"
            
        timeout_val = timeout if timeout is not None else self.timeout
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=timeout_val)
            resp.raise_for_status()
            result_json = resp.json()
            return result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.error(f"[Gemini] Generate failed: {e}", exc_info=True)
            raise e
