from typing import Any, AsyncGenerator, Dict, List, Optional

class BaseProvider:
    """Interface for LLM providers inside VOID."""
    
    async def chat(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> str:
        """Asynchronously send a chat request and return the full response."""
        raise NotImplementedError("chat method not implemented")
        
    async def chat_stream(self, history: List[Dict[str, str]], prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Asynchronously send a chat request and yield chunks of response text."""
        raise NotImplementedError("chat_stream method not implemented")
        
    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        """Synchronously generate a response using a /generate endpoint."""
        raise NotImplementedError("generate method not implemented")
        
    async def available(self) -> bool:
        """Check if the provider service is operational and reachable."""
        raise NotImplementedError("available method not implemented")
