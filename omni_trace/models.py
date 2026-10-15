"""
Data structures and Pydantic models for OmniTrace execution traces,
tool outputs, and agent states.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    """Normalized payload returned by all OmniTrace tools."""
    tool_name: str
    success: bool
    data: Any = None
    row_count: int = 0
    is_empty: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_observation_string(self) -> str:
        """Converts tool result into an informative observation string for the LLM."""
        if not self.success:
            return f"❌ [TOOL ERROR in {self.tool_name}]: {self.error}"
        if self.is_empty:
            msg = self.metadata.get("message", "No matching records found.")
            return f"⚠️ [TOOL OBSERVATION - EMPTY RESULT]: {msg}"
        return f"✅ [TOOL OBSERVATION]: {self.data}"

class AgentAction(BaseModel):
    """Represents a discrete tool invocation decided by the agent."""
    tool_name: str
    tool_args: Dict[str, Any]
    thought: Optional[str] = None

class AgentStep(BaseModel):
    """A single ReAct step in the reasoning chain."""
    step_number: int
    thought: str
    action: Optional[AgentAction] = None
    observation: Optional[str] = None
    error_detected: bool = False
    self_healed: bool = False

class AgentTrace(BaseModel):
    """Complete execution record for a user query."""
    query: str
    final_answer: str
    steps: List[AgentStep] = Field(default_factory=list)
    tools_called: List[str] = Field(default_factory=list)
    self_healing_count: int = 0
    total_tokens_used: int = 0
    execution_time_sec: float = 0.0
    status: str = "COMPLETED"  # "COMPLETED", "MAX_STEPS_EXCEEDED", "ERROR"
