from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState

def human_approval_node(state: AgentState) -> Dict[str, Any]:
    remediation = state.get("proposed_remediation", "")
    service = state.get("service_name", "service")

    msg = (
        f"[HUMAN-IN-THE-LOOP APPROVAL GRANTED] Remediation for {service} approved: '{remediation}'."
    )
    return {
        "human_approved": True,
        "messages": [AIMessage(content=msg)]
    }
