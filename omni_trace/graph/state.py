from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Typed state representation for OmniTrace LangGraph state machine.
    Uses Annotated with add_messages for conversation history and explicit keys
    for discrete node updates.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    incident_query: str
    service_name: Optional[str]
    target_metric: Optional[str]
    telemetry_summary: Dict[str, Any]
    retrieved_runbooks: List[Dict[str, Any]]
    diagnostic_hypothesis: str
    proposed_remediation: str
    critic_verdict: str  # 'PASS' | 'REFINE' | 'FAIL'
    groundedness_score: float
    retry_count: int
    is_sensitive_action: bool
    human_approved: bool
    final_report: str
