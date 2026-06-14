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
from backend.providers.openai_compatible import OpenAICompatibleProvider
from backend.providers.gemini_compatible import GeminiProvider
from backend.providers.anthropic_compatible import AnthropicProvider

logger = logging.getLogger("void.providers.router")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = ROOT_DIR / "memory" / "data" / "llm_config.json"

class MultiModelRouter(BaseProvider):
    def __init__(self):
        self.config_path = CONFIG_PATH
        self.config = {
            "routing_mode": "AUTO",  # AUTO, LOCAL, CLOUD, OPENAI, GEMINI, ANTHROPIC
            "active_provider": "ollama",
            "fallback_enabled": True,
            # Ollama / Local
            "local_model": "qwen2.5:0.5b",
            "ollama_base_url": "http://127.0.0.1:11434",
            # OpenAI
            "openai_api_key": "",
            "openai_model": "gpt-4o",
            "openai_base_url": "https://api.openai.com/v1",
            # Gemini
            "gemini_api_key": "",
            "gemini_model": "gemini-1.5-flash",
            "gemini_base_url": "https://generativelanguage.googleapis.com/v1beta",
            # Anthropic
            "anthropic_api_key": "",
            "anthropic_model": "claude-3-5-sonnet-20241022",
            "anthropic_base_url": "https://api.anthropic.com/v1",
            # Kimi
            "kimi_api_key": "",
            "kimi_model": "kimi-k2.7-code"
        }
        self.load_config()
        self.initialize_providers()
        
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

    def initialize_providers(self):
        self.ollama_provider = OllamaProvider(
            model=self.config["local_model"],
            base_url=self.config.get("ollama_base_url", "http://127.0.0.1:11434")
        )
        self.openai_provider = OpenAICompatibleProvider(
            api_key=self.config.get("openai_api_key", ""),
            model=self.config.get("openai_model", "gpt-4o"),
            base_url=self.config.get("openai_base_url", "https://api.openai.com/v1")
        )
        self.gemini_provider = GeminiProvider(
            api_key=self.config.get("gemini_api_key", ""),
            model=self.config.get("gemini_model", "gemini-1.5-flash"),
            base_url=self.config.get("gemini_base_url", "https://generativelanguage.googleapis.com/v1beta")
        )
        self.anthropic_provider = AnthropicProvider(
            api_key=self.config.get("anthropic_api_key", ""),
            model=self.config.get("anthropic_model", "claude-3-5-sonnet-20241022"),
            base_url=self.config.get("anthropic_base_url", "https://api.anthropic.com/v1")
        )
        self.kimi_provider = KimiProvider(
            api_key=self.config.get("kimi_api_key", ""),
            model=self.config.get("kimi_model", "kimi-k2.7-code")
        )

    def update_config(self, new_config: Dict[str, Any]):
        self.config.update(new_config)
        self.save_config()
        self.initialize_providers()

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
                "has_api_key": bool(self.config["kimi_api_key"]) or bool(self.config["openai_api_key"]) or bool(self.config["gemini_api_key"]) or bool(self.config["anthropic_api_key"])
            }
        }

    def classify_query(self, user_text: str) -> Tuple[bool, str]:
        """
        Classifies if the query warrants Kimi K2.7 Code or deep engineering.
        Returns: (is_coding, reason)
        """
        text_lower = user_text.lower().strip()
        
        if "```" in user_text:
            return True, "User prompt contains markdown code blocks"
            
        project_keywords = [
            "analyze project", "project structure", "architecture", "explain codebase", 
            "codebase map", "find bugs", "improve architecture", "review code", 
            "explain codebase", "add voice authentication", "modify void", 
            "rewrite module", "improve module", "self-repair", "refactor code", 
            "git changes", "diagnostics logs", "voice authentication"
        ]
        if any(kw in text_lower for kw in project_keywords):
            return True, "Matches project analysis keywords"
            
        coding_verbs = ["debug", "write code", "create function", "refactor", "compile error", "fastapi route", "implement feature", "unit test", "syntax error"]
        if any(v in text_lower for v in coding_verbs):
            return True, "Matches coding action verbs"
            
        programming_keywords = [
            "python", "javascript", "electron", "fastapi", "sqlite", "html", "css", 
            "import ", "def ", "class ", "return ", "struct ", "package.json", "requirements.txt",
            "async ", "await ", "except ", "try:", "npm install", "pip install"
        ]
        if any(kw in text_lower for kw in programming_keywords):
            return True, "Matches programming language keywords"

        return False, "General conversation / command"

    def select_provider_and_model(self, user_text: str) -> Tuple[str, BaseProvider, str, str]:
        """
        Routes the query to the correct provider and selects/updates the model name.
        Returns: (provider_name, provider_instance, model_name, routing_reason)
        """
        mode = self.config["routing_mode"].upper()
        
        # 1. Manual Overrides
        if mode == "LOCAL" or mode == "OLLAMA":
            return "Local", self.ollama_provider, self.config["local_model"], "Manual Ollama configuration"
        elif mode == "OPENAI":
            return "OpenAI", self.openai_provider, self.config["openai_model"], "Manual OpenAI configuration"
        elif mode == "GEMINI":
            return "Gemini", self.gemini_provider, self.config["gemini_model"], "Manual Gemini configuration"
        elif mode == "ANTHROPIC":
            return "Anthropic", self.anthropic_provider, self.config["anthropic_model"], "Manual Anthropic configuration"
        elif mode == "CLOUD" or mode == "KIMI":
            return "Cloud", self.kimi_provider, self.config["kimi_model"], "Manual Kimi configuration"
        
        # 2. AUTO Mode: dynamic routing based on classification
        discovered = self.ollama_provider.discover_and_categorize_models()
        text_lower = user_text.lower().strip()
        is_coding, coding_reason = self.classify_query(user_text)
        
        # Check for reasoning/planning queries
        reasoning_keywords = ["reason", "prove", "math", "why", "logic", "solve", "step by step", "algorithm"]
        is_reasoning = any(k in text_lower for k in reasoning_keywords)
        
        # Check for vision queries
        vision_keywords = ["screenshot", "screen", "camera", "image", "picture", "photo", "look at my screen"]
        is_vision = any(k in text_lower for k in vision_keywords)
        
        # Check for quick questions (short text)
        is_quick = len(text_lower.split()) <= 5
        
        if is_coding:
            if self.config.get("kimi_api_key"):
                return "Cloud", self.kimi_provider, self.config["kimi_model"], f"Coding task: {coding_reason} -> Moonshot Kimi"
            elif self.config.get("openai_api_key"):
                return "OpenAI", self.openai_provider, self.config["openai_model"], f"Coding task: {coding_reason} -> OpenAI"
            elif discovered.get("Coding"):
                best_local_coder = discovered["Coding"][0]
                self.ollama_provider.model = best_local_coder
                return "Local", self.ollama_provider, best_local_coder, f"Coding task: {coding_reason} -> Dynamic Local Coder ({best_local_coder})"
            
        elif is_reasoning:
            if discovered.get("Reasoning"):
                best_reasoner = discovered["Reasoning"][0]
                self.ollama_provider.model = best_reasoner
                return "Local", self.ollama_provider, best_reasoner, f"Reasoning task -> Dynamic Local Reasoner ({best_reasoner})"
            elif self.config.get("openai_api_key"):
                return "OpenAI", self.openai_provider, self.config["openai_model"], "Reasoning task -> OpenAI"
                
        elif is_vision:
            if self.config.get("gemini_api_key"):
                return "Gemini", self.gemini_provider, self.config["gemini_model"], "Vision task -> Gemini"
            elif discovered.get("Vision"):
                best_vision = discovered["Vision"][0]
                self.ollama_provider.model = best_vision
                return "Local", self.ollama_provider, best_vision, f"Vision task -> Dynamic Local Vision ({best_vision})"
                
        elif is_quick:
            if discovered.get("Lightweight"):
                best_light = discovered["Lightweight"][0]
                self.ollama_provider.model = best_light
                return "Local", self.ollama_provider, best_light, f"Quick question -> Dynamic Local Lightweight ({best_light})"
        
        # Default fallback
        active_prov = self.config.get("active_provider", "ollama").lower()
        if active_prov == "openai" and self.config.get("openai_api_key"):
            return "OpenAI", self.openai_provider, self.config["openai_model"], "Default Auto routing -> OpenAI"
        elif active_prov == "gemini" and self.config.get("gemini_api_key"):
            return "Gemini", self.gemini_provider, self.config["gemini_model"], "Default Auto routing -> Gemini"
        elif active_prov == "anthropic" and self.config.get("anthropic_api_key"):
            return "Anthropic", self.anthropic_provider, self.config["anthropic_model"], "Default Auto routing -> Anthropic"
            
        return "Local", self.ollama_provider, self.config["local_model"], "Default Auto routing -> Local Ollama"

    def select_provider(self, user_text: str) -> Tuple[str, BaseProvider, str]:
        prov_name, prov, _, reason = self.select_provider_and_model(user_text)
        return prov_name, prov, reason

    async def available(self) -> bool:
        mode = self.config["routing_mode"].upper()
        if mode == "LOCAL" or mode == "OLLAMA":
            return await self.ollama_provider.available()
        elif mode == "OPENAI":
            return await self.openai_provider.available()
        elif mode == "GEMINI":
            return await self.gemini_provider.available()
        elif mode == "ANTHROPIC":
            return await self.anthropic_provider.available()
        elif mode == "CLOUD" or mode == "KIMI":
            return await self.kimi_provider.available()
        else:
            return await self.ollama_provider.available()

    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        provider_name, provider, model_name, reason = self.select_provider_and_model(prompt)
        
        total_chars = len(prompt) + (len(system_prompt) if system_prompt else 0)
        for msg in history:
            total_chars += len(msg.get("content", ""))
        estimated_tokens = int(total_chars / 4)
        
        t_start = time.perf_counter()
        
        logger.info(f"[ROUTER] Selected provider: {provider_name} | Model: {model_name} | Reason: {reason} | Context: ~{estimated_tokens} tokens")
        print(f"[ROUTER] Routing to {provider_name} ({reason})")

        try:
            res = await provider.chat(history, prompt, system_prompt=system_prompt)
            
            # Record metrics
            self.metrics["last_provider"] = provider_name
            self.metrics["last_model"] = model_name
            self.metrics["last_context_tokens"] = estimated_tokens
            self.metrics["last_latency_seconds"] = time.perf_counter() - t_start
            self.metrics["last_routing_reason"] = reason
            
            print(f"[MODEL] Selected: {self.metrics['last_model']} | Context: {estimated_tokens} tokens | Response duration: {self.metrics['last_latency_seconds']:.2f}s")
            return res
        except Exception as e:
            logger.error(f"[ROUTER] Provider {provider_name} failed: {e}")
            if provider_name != "Local" and self.config["fallback_enabled"]:
                logger.warning(f"[CLOUD FALLBACK] Provider {provider_name} failed. Redirecting to Ollama Local model. Reason: {e}")
                print(f"[CLOUD FALLBACK] Provider failed. Switching to Local model {self.config['local_model']}...")
                
                t_fallback_start = time.perf_counter()
                try:
                    local_res = await self.ollama_provider.chat(history, prompt, system_prompt=system_prompt)
                    
                    self.metrics["last_provider"] = "Local (Fallback)"
                    self.metrics["last_model"] = self.config["local_model"]
                    self.metrics["last_context_tokens"] = estimated_tokens
                    self.metrics["last_latency_seconds"] = time.perf_counter() - t_fallback_start
                    self.metrics["last_routing_reason"] = f"Provider {provider_name} Failed ({e})"
                    
                    notice = f"*(System Notice: Provider {provider_name} is currently unavailable. I have automatically redirected your request to the local model so your session remains uninterrupted, Sir.)*\n\n"
                    return notice + local_res
                except Exception as local_err:
                    logger.error(f"[ROUTER] Fallback local provider also failed: {local_err}")
                    return "My apologies, Sir. Both the cloud engine and the local Ollama service are unresponsive. Please ensure Ollama is running."
            raise e

    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        provider_name, provider, model_name, reason = self.select_provider_and_model(prompt)
        
        total_chars = len(prompt) + (len(system_prompt) if system_prompt else 0)
        for msg in history:
            total_chars += len(msg.get("content", ""))
        estimated_tokens = int(total_chars / 4)
        
        t_start = time.perf_counter()
        logger.info(f"[ROUTER-STREAM] Routing to {provider_name} | Model: {model_name} ({reason})")
        print(f"[ROUTER-STREAM] Routing to {provider_name} ({reason})")

        try:
            self.metrics["last_provider"] = provider_name
            self.metrics["last_model"] = model_name
            self.metrics["last_context_tokens"] = estimated_tokens
            self.metrics["last_routing_reason"] = reason

            async for token in provider.chat_stream(history, prompt, system_prompt=system_prompt):
                yield token
                
            self.metrics["last_latency_seconds"] = time.perf_counter() - t_start
        except Exception as e:
            logger.error(f"[ROUTER-STREAM] Stream failed: {e}")
            if provider_name != "Local" and self.config["fallback_enabled"]:
                logger.warning(f"[CLOUD FALLBACK-STREAM] Cloud failed. Switching to Local model...")
                yield f"*(System Notice: Provider {provider_name} disconnected. Switching to local Ollama model...)*\n\n"
                
                t_fallback_start = time.perf_counter()
                try:
                    async for token in self.ollama_provider.chat_stream(history, prompt, system_prompt=system_prompt):
                        yield token
                    self.metrics["last_provider"] = "Local (Fallback)"
                    self.metrics["last_model"] = self.config["local_model"]
                    self.metrics["last_latency_seconds"] = time.perf_counter() - t_fallback_start
                except Exception as local_err:
                    logger.error(f"[ROUTER-STREAM] Fallback stream also failed: {local_err}")
                    yield "\n\n[System Error: Both remote provider and local Ollama stream requests failed.]"
            else:
                raise e

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        provider_name, provider, model_name, reason = self.select_provider_and_model(prompt)
        
        t_start = time.perf_counter()
        try:
            res = provider.generate(prompt, system_prompt=system_prompt, format=format, timeout=timeout)
            self.metrics["last_provider"] = provider_name
            self.metrics["last_model"] = model_name
            self.metrics["last_latency_seconds"] = time.perf_counter() - t_start
            return res
        except Exception as e:
            logger.error(f"[ROUTER] Generate failed: {e}")
            if provider_name != "Local" and self.config["fallback_enabled"]:
                try:
                    return self.ollama_provider.generate(prompt, system_prompt=system_prompt, format=format, timeout=timeout)
                except Exception:
                    pass
            raise e
