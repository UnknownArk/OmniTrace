import re
from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState

KNOWN_SERVICES = ["checkout-service", "payment-gateway", "auth-service", "inventory-service"]

def router_node(state: AgentState) -> Dict[str, Any]:
    query = state.get("incident_query", "").lower()

    detected_service = None
    for service in KNOWN_SERVICES:
        if service in query or service.replace("-", " ") in query:
            detected_service = service
            break

    if not detected_service:
        if "checkout" in query or "pay" in query:
            detected_service = "checkout-service"
        elif "auth" in query or "token" in query or "login" in query:
            detected_service = "auth-service"
        elif "gateway" in query or "acquirer" in query:
            detected_service = "payment-gateway"

    thought = f"Identified target service: {detected_service or 'global'}. Routing to hybrid telemetry and runbook retrieval."
    return {
        "service_name": detected_service,
        "messages": [AIMessage(content=thought)]
    }
