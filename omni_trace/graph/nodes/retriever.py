from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState
from omni_trace.database.vector_store import get_vector_store

def retriever_node(state: AgentState) -> Dict[str, Any]:
    query = state.get("incident_query", "")
    service = state.get("service_name")

    store = get_vector_store()
    matches = store.search(query=query, service_name=service, top_k=2)

    msg = f"Retrieved {len(matches)} runbook(s) for service '{service}'."
    return {
        "retrieved_runbooks": matches,
        "messages": [AIMessage(content=msg)]
    }
