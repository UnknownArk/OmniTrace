from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState

def refine_query_node(state: AgentState) -> Dict[str, Any]:
    current_query = state.get("incident_query", "")
    service = state.get("service_name", "")
    attempt = state.get("retry_count", 1)

    # Broaden query with downstream keywords
    refined_query = f"{current_query} {service} timeout latency connection failure"
    msg = f"Critic requested query refinement (Cycle {attempt}). Broadened search to: '{refined_query}'"

    return {
        "incident_query": refined_query,
        "messages": [AIMessage(content=msg)]
    }
