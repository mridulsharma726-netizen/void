"""
VOID Unified BaseTool Contract
=============================

All consolidated tools inherit from this class to ensure consistent metadata, timeouts,
and standardized execution results.
"""

from typing import Dict, Any
import abc

class BaseTool(abc.ABC):
    """
    Abstract Base Class for all VOID consolidated tools.
    """
    
    def __init__(self, name: str, description: str, timeout: int = 60):
        self.name = name
        self.description = description
        self.timeout = timeout

    @abc.abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool action asynchronously.
        
        Args:
            **kwargs: Arbitrary keyword arguments passed to the tool.
            
        Returns:
            Dict: Standardized structure:
                {
                    "status": "ok" | "error",
                    "output": "human readable output string",
                    "raw": {...}
                }
        """
        pass
