import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from backend.providers.base import BaseProvider
from backend.providers.ollama_local import OllamaProvider
from backend.providers.kimi_cloud import KimiProvider

logger = logging.getLogger("void.providers.router")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = ROOT_DIR / "memory" / "data" / "llm_config.json"

class MultiModelRouter(BaseProvider):
    def __init__(self):
        self.config_path = CONFIG_PATH
        self.config = {
            "routing_mode": "AUTO",  # AUTO, LOCAL, CLOUD
            "kimi_api_key": "",
            "kimi_model": "kimi-k2.7-code",
            "local_model": "qwen2.5:0.5b",
            "fallback_enabled": True
        }
        self.load_config()
        self.ollama_provider = OllamaProvider(model=self.config["local_model"])
        self.kimi_provider = KimiProvider(api_key=self.config["kimi_api_key"], model=self.config["kimi_model"])
        
        # Performance metrics
        self.metrics = {
            "last_model": "None",
            "last_provider": "None",
            "last_context_tokens": 0,
            "last_latency_seconds": 0.0,
            "last_routing_reason": "None"
        }

    def load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except Exception as e:
                logger.error(f"Failed to load LLM config: {e}")
        else:
            self.save_config()

    def save_config(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save LLM config: {e}")

    def update_config(self, new_config: Dict[str, Any]):
        self.config.update(new_config)
        self.save_config()
        # Re-initialize providers with updated configs
        self.ollama_provider = OllamaProvider(model=self.config["local_model"])
        self.kimi_provider = KimiProvider(api_key=self.config["kimi_api_key"], model=self.config["kimi_model"])

    def get_metrics(self) -> Dict[str, Any]:
        """Return metrics for the model dashboard panel."""
        import psutil
        
        # Calculate local memory usage estimation
        python_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        local_model = self.config["local_model"].lower()
        
        # Estimate additional model memory usage based on Ollama model sizes
        model_memory = 0
        if self.metrics["last_provider"] == "Local":
            if "0.5b" in local_model:
                model_memory = 380
            elif "1.5b" in local_model:
                model_memory = 980
            elif "3b" in local_model or "3.2b" in local_model:
                model_memory = 2000
            elif "mistral" in local_model or "7b" in local_model:
                model_memory = 4500
            else:
                model_memory = 1500

        total_memory_usage_mb = python_mem + model_memory
        
        return {
            "model": self.metrics["last_model"] if self.metrics["last_model"] != "None" else self.config["local_model"],
            "provider": self.metrics["last_provider"] if self.metrics["last_provider"] != "None" else "Local",
            "context_size": self.metrics["last_context_tokens"],
            "response_time": f"{self.metrics['last_latency_seconds']:.2f}s",
            "memory_usage": f"{total_memory_usage_mb:.1f} MB",
            "config": {
                "routing_mode": self.config["routing_mode"],
                "local_model": self.config["local_model"],
                "kimi_model": self.config["kimi_model"],
                "fallback_enabled": self.config["fallback_enabled"],
                "has_api_key": bool(self.config["kimi_api_key"])
            }
        }

    def classify_query(self, user_text: str) -> Tuple[bool, str]:
        """
        Classifies if the query warrants Kimi K2.7 Code.
        Returns: (is_coding, reason)
        """
        text_lower = user_text.lower().strip()
        
        # 1. Check if user query contains explicit code markers
        if "```" in user_text:
            return True, "User prompt contains markdown code blocks"
            
        # 2. Key codebase/project keywords
        project_keywords = [
            "analyze project", "project structure", "architecture", "explain codebase", 
            "codebase map", "find bugs", "improve architecture", "review code", 
            "explain codebase", "add voice authentication", "modify void", 
            "rewrite module", "improve module", "self-repair", "refactor code", 
            "git changes", "diagnostics logs", "voice authentication"
        ]
        if any(kw in text_lower for kw in project_keywords):
            return True, "Matches project analysis keywords"
            
        # 3. Direct coding indicators
        coding_verbs = ["debug", "write code", "create function", "refactor", "compile error", "fastapi route", "implement feature", "unit test", "syntax error"]
        if any(v in text_lower for v in coding_verbs):
            return True, "Matches coding action verbs"

        # 4. Programming language context keywords
        programming_keywords = [
            "python", "javascript", "electron", "fastapi", "sqlite", "html", "css", 
            "import ", "def ", "class ", "return ", "struct ", "package.json", "requirements.txt",
            "async ", "await ", "except ", "try:", "npm install", "pip install"
        ]
        if any(kw in text_lower for kw in programming_keywords):
            return True, "Matches programming language keywords"

        return False, "General conversation / command"

    def select_provider(self, user_text: str) -> Tuple[str, BaseProvider, str]:
        """
        Routes the query to the correct provider.
        Returns: (provider_name, provider_instance, routing_reason)
        """
        mode = self.config["routing_mode"].upper()
        
        if mode == "LOCAL":
            return "Local", self.ollama_provider, "Manual Local routing config"
        elif mode == "CLOUD":
            if not self.config["kimi_api_key"]:
                return "Local", self.ollama_provider, "Kimi Cloud requested but API key is missing. Routing to Local."
            return "Cloud", self.kimi_provider, "Manual Cloud routing config"
        else:
            # AUTO Mode: classify intent
            is_coding, reason = self.classify_query(user_text)
            if is_coding:
                if not self.config["kimi_api_key"]:
                    return "Local", self.ollama_provider, f"Coding task detected ({reason}) but Kimi API key is missing. Routing to Local."
                return "Cloud", self.kimi_provider, f"Coding task detected: {reason}"
            else:
                return "Local", self.ollama_provider, "Casual conversation / command detected"

    async def available(self) -> bool:
        mode = self.config["routing_mode"].upper()
        if mode == "LOCAL":
            return await self.ollama_provider.available()
        elif mode == "CLOUD":
            return await self.kimi_provider.available()
        else:
            return await self.ollama_provider.available() or await self.kimi_provider.available()

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        provider_name, provider, reason = self.select_provider(prompt)
        
        # Estimate context token size (approx. 4 characters per token as a rough metric)
        total_chars = len(prompt) + (len(system_prompt) if system_prompt else 0)
        for msg in history:
            total_chars += len(msg.get("content", ""))
        estimated_tokens = int(total_chars / 4)
        
        t_start = time.perf_counter()
        
        # Logging statement
        logger.info(f"[ROUTER] Selected provider: {provider_name} | Reason: {reason} | Context: ~{estimated_tokens} tokens")
        print(f"[ROUTER] Routing to {provider_name} ({reason})")

        try:
            res = await provider.chat(history, prompt, system_prompt=system_prompt)
            
            # Record metrics
            self.metrics["last_provider"] = provider_name
            self.metrics["last_model"] = self.config["kimi_model"] if provider_name == "Cloud" else self.config["local_model"]
            self.metrics["last_context_tokens"] = estimated_tokens
            self.metrics["last_latency_seconds"] = time.perf_counter() - t_start
            self.metrics["last_routing_reason"] = reason
            
            # Print latency logs
            print(f"[MODEL] Selected: {self.metrics['last_model']} | Context: {estimated_tokens} tokens | Response duration: {self.metrics['last_latency_seconds']:.2f}s")
            
            return res
        except Exception as e:
            logger.error(f"[ROUTER] Provider {provider_name} failed: {e}")
            if provider_name == "Cloud" and self.config["fallback_enabled"]:
                # Log fallback
                logger.warning(f"[CLOUD FALLBACK] Kimi Cloud failed. Redirecting to Ollama Local model. Reason: {e}")
                print(f"[CLOUD FALLBACK] Cloud failed. Switching to Local model {self.config['local_model']}...")
                
                t_fallback_start = time.perf_counter()
                try:
                    local_res = await self.ollama_provider.chat(history, prompt, system_prompt=system_prompt)
                    
                    self.metrics["last_provider"] = "Local (Fallback)"
                    self.metrics["last_model"] = self.config["local_model"]
                    self.metrics["last_context_tokens"] = estimated_tokens
                    self.metrics["last_latency_seconds"] = time.perf_counter() - t_fallback_start
                    self.metrics["last_routing_reason"] = f"Kimi Cloud Failed ({e})"
                    
                    notice = "*(System Notice: Moonshot Kimi Cloud is currently unavailable. I have automatically redirected your engineering request to the local model so your session remains uninterrupted, Sir.)*\n\n"
                    return notice + local_res
                except Exception as local_err:
                    logger.error(f"[ROUTER] Fallback local provider also failed: {local_err}")
                    return "My apologies, Sir. Both the cloud engine and the local Ollama service are unresponsive. Please ensure Ollama is running."
            raise e

    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        provider_name, provider, reason = self.select_provider(prompt)
        
        total_chars = len(prompt) + (len(system_prompt) if system_prompt else 0)
        for msg in history:
            total_chars += len(msg.get("content", ""))
        estimated_tokens = int(total_chars / 4)
        
        t_start = time.perf_counter()
        logger.info(f"[ROUTER-STREAM] Routing to {provider_name} ({reason})")
        print(f"[ROUTER-STREAM] Routing to {provider_name} ({reason})")

        try:
            # We record metrics on connection start
            self.metrics["last_provider"] = provider_name
            self.metrics["last_model"] = self.config["kimi_model"] if provider_name == "Cloud" else self.config["local_model"]
            self.metrics["last_context_tokens"] = estimated_tokens
            self.metrics["last_routing_reason"] = reason

            async for token in provider.chat_stream(history, prompt, system_prompt=system_prompt):
                yield token
                
            self.metrics["last_latency_seconds"] = time.perf_counter() - t_start
        except Exception as e:
            logger.error(f"[ROUTER-STREAM] Stream failed: {e}")
            if provider_name == "Cloud" and self.config["fallback_enabled"]:
                logger.warning(f"[CLOUD FALLBACK-STREAM] Cloud failed. Switching to Local model...")
                yield "*(System Notice: Moonshot Kimi Cloud has disconnected. Switching to local Ollama model...)*\n\n"
                
                t_fallback_start = time.perf_counter()
                try:
                    async for token in self.ollama_provider.chat_stream(history, prompt, system_prompt=system_prompt):
                        yield token
                    self.metrics["last_provider"] = "Local (Fallback)"
                    self.metrics["last_model"] = self.config["local_model"]
                    self.metrics["last_latency_seconds"] = time.perf_counter() - t_fallback_start
                except Exception as local_err:
                    logger.error(f"[ROUTER-STREAM] Fallback stream also failed: {local_err}")
                    yield "\n\n[System Error: Both Kimi Cloud and local Ollama stream requests failed.]"
            else:
                raise e

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        provider_name, provider, reason = self.select_provider(prompt)
        
        t_start = time.perf_counter()
        try:
            res = provider.generate(prompt, system_prompt=system_prompt, format=format, timeout=timeout)
            
            self.metrics["last_provider"] = provider_name
            self.metrics["last_model"] = self.config["kimi_model"] if provider_name == "Cloud" else self.config["local_model"]
            self.metrics["last_latency_seconds"] = time.perf_counter() - t_start
            return res
        except Exception as e:
            logger.error(f"[ROUTER] Generate failed: {e}")
            if provider_name == "Cloud" and self.config["fallback_enabled"]:
                try:
                    return self.ollama_provider.generate(prompt, system_prompt=system_prompt, format=format, timeout=timeout)
                except Exception:
                    pass
            raise e
