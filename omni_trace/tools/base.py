"""
Base classes and interfaces for OmniTrace tools.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict
from omni_trace.models import ToolResult

class BaseTool(ABC):
    """Abstract base class for all OmniTrace tools."""

    name: str
    description: str

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Executes the tool logic and returns a normalized ToolResult."""
        pass

    def __call__(self, **kwargs) -> Dict[str, Any]:
        """Wrapper to return a standard dictionary payload for the LLM tool call."""
        result = self.execute(**kwargs)
        return result.model_dump()
