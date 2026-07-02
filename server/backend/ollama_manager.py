import os
import time
import socket
import logging
import subprocess
import threading
import requests
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("void.ollama_manager")

class OllamaConnectionManager:
    """
    Automatic Ollama Connection Manager.
    
    Detects if Ollama is running, attempts to start it if offline,
    automatically loads and verifies the preferred model, and
    retries with exponential backoff.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, check_interval: float = 10.0):
        if self._initialized:
            return
        self._initialized = True
        self.check_interval = check_interval
        self.status = "offline"  # connected, connecting, offline, model_missing
        self.error_message = ""
        self.active_model = ""
        self.base_url = "http://127.0.0.1:11434"
        self.process = None
        self._running = False
        self._thread = None
        self._status_lock = threading.Lock()
        
    def start(self):
        """Starts the background monitoring thread."""
        with self._status_lock:
            if self._running:
                return
            self._running = True
            
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="VOID-OllamaMonitor")
        self._thread.start()
        logger.info("[OLLAMA MANAGER] Background monitor started.")

    def stop(self):
        """Stops the background monitoring thread."""
        with self._status_lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("[OLLAMA MANAGER] Background monitor stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Returns the current connection status and metadata."""
        with self._status_lock:
            return {
                "status": self.status,
                "active_model": self.active_model,
                "error_message": self.error_message,
                "base_url": self.base_url
            }

    def _is_port_open(self, host: str = "127.0.0.1", port: int = 11434) -> bool:
        """Checks if a local port is open."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect((host, port))
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False

    def _get_preferred_model(self) -> str:
        """Retrieves the preferred model from the LLM router config."""
        try:
            from backend.providers.router import MultiModelRouter
            router = MultiModelRouter()
            return router.config.get("local_model", "qwen2.5:0.5b")
        except Exception:
            return "qwen2.5:0.5b"

    def _start_ollama_service(self):
        """Attempts to start the Ollama service in the background."""
        logger.info("[OLLAMA MANAGER] Ollama is offline. Attempting to start the service...")
        try:
            # Try running 'ollama serve'
            # On Windows, we can use CREATE_NO_WINDOW if we want to run silently,
            # but shell=True or subprocess.Popen works fine.
            startupinfo = None
            if os.name == 'nt':
                # Prevents a cmd window from flashing
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                close_fds=True
            )
            logger.info("[OLLAMA MANAGER] Spawned 'ollama serve' process.")
        except Exception as e:
            logger.error(f"[OLLAMA MANAGER] Failed to start Ollama process: {e}")

    def check_connection(self) -> bool:
        """Synchronously check connection, start if offline, and verify model."""
        preferred_model = self._get_preferred_model()
        self.active_model = preferred_model
        
        # 1. Check if port is open
        if not self._is_port_open():
            with self._status_lock:
                self.status = "connecting"
                self.error_message = "Ollama service is offline. Attempting auto-start..."
                
            self._start_ollama_service()
            
            # Wait with exponential backoff
            backoff = 0.5
            max_wait = 15.0
            elapsed = 0.0
            success = False
            
            while elapsed < max_wait:
                time.sleep(backoff)
                elapsed += backoff
                if self._is_port_open():
                    success = True
                    break
                backoff = min(backoff * 2, 4.0)
                
            if not success:
                with self._status_lock:
                    self.status = "offline"
                    self.error_message = "Ollama service is offline and failed to start automatically. Please ensure Ollama is installed and running."
                return False

        # 2. Verify model availability
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                # Check exact match or :latest tag
                model_exists = (preferred_model in models) or (f"{preferred_model}:latest" in models)
                
                # Also check base model names (e.g., if it's "qwen2.5:0.5b" and tags show "qwen2.5:0.5b")
                if not model_exists:
                    # Let's see if any model matches
                    for m in models:
                        if m.startswith(preferred_model) or preferred_model.startswith(m):
                            model_exists = True
                            self.active_model = m
                            break
                            
                if model_exists:
                    with self._status_lock:
                        self.status = "connected"
                        self.error_message = ""
                    return True
                else:
                    with self._status_lock:
                        self.status = "model_missing"
                        self.error_message = f"Preferred model '{preferred_model}' is not installed in Ollama.\n\nTo download, open a terminal and run:\n  ollama pull {preferred_model}"
                    logger.warning(f"[OLLAMA MANAGER] Preferred model '{preferred_model}' is missing.")
                    return False
            else:
                with self._status_lock:
                    self.status = "offline"
                    self.error_message = f"Ollama API returned unexpected status code: {resp.status_code}"
                return False
        except Exception as e:
            with self._status_lock:
                self.status = "offline"
                self.error_message = f"Failed to communicate with Ollama API: {e}"
            return False

    def _monitor_loop(self):
        """Background loop that periodically checks the connection."""
        # Initial check on start
        self.check_connection()
        
        while True:
            with self._status_lock:
                if not self._running:
                    break
            try:
                self.check_connection()
            except Exception as e:
                logger.error(f"[OLLAMA MANAGER] Error in monitor loop: {e}")
                
            # Sleep in small steps to react quickly to stop signal
            for _ in range(int(self.check_interval * 2)):
                with self._status_lock:
                    if not self._running:
                        break
                time.sleep(0.5)

# Global singleton
ollama_manager = OllamaConnectionManager()
