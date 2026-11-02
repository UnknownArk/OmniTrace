from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState

def synthesis_node(state: AgentState) -> Dict[str, Any]:
    telemetry = state.get("telemetry_summary", {})
    runbooks = state.get("retrieved_runbooks", [])
    service = state.get("service_name", "unknown")

    error_events = telemetry.get("error_events", [])
    matched_runbook = runbooks[0] if runbooks else {}

    if not error_events:
        hypothesis = f"No critical telemetry errors detected for service '{service}'. Metrics indicate healthy baseline."
        remediation = "Continue monitoring telemetry. No immediate mitigation required."
        is_sensitive = False
    else:
        top_err = error_events[0]
        code = top_err.get("status_code")
        err_msg = top_err.get("error_message") or "Unknown error"
        max_lat = top_err.get("max_latency", 0)

        hypothesis = (
            f"Service '{service}' is failing with HTTP {code} (peak latency: {max_lat:.1f}ms). "
            f"Telemetry indicates: '{err_msg}'. "
            f"Aligned with runbook: '{matched_runbook.get('title', 'Generic Incident')}'."
        )

        remediation = matched_runbook.get("content", "").split("REMEDIATION:")[-1].strip()
        if not remediation:
            remediation = f"Review deployment logs for {service} and verify downstream network dependencies."

        sensitive_triggers = ["kubectl", "restart", "rollback", "trip", "kill", "purge", "scale"]
        is_sensitive = any(trigger in remediation.lower() for trigger in sensitive_triggers)

    msg = f"Synthesized diagnosis for {service}. Sensitive action: {is_sensitive}."
    return {
        "diagnostic_hypothesis": hypothesis,
        "proposed_remediation": remediation,
        "is_sensitive_action": is_sensitive,
        "messages": [AIMessage(content=msg)]
    }
