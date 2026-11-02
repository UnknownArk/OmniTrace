from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState

def critic_node(state: AgentState) -> Dict[str, Any]:
    hypothesis = state.get("diagnostic_hypothesis", "")
    remediation = state.get("proposed_remediation", "")
    telemetry = state.get("telemetry_summary", {})
    runbooks = state.get("retrieved_runbooks", [])
    retry_count = state.get("retry_count", 0)

    # Groundedness checks
    score = 0.0

    # Check 1: Telemetry alignment (Has status code and real error data)
    error_events = telemetry.get("error_events", [])
    if error_events:
        top_code = str(error_events[0].get("status_code", ""))
        if top_code and top_code in hypothesis:
            score += 0.4
    else:
        if "healthy" in hypothesis.lower() or "no critical" in hypothesis.lower():
            score += 0.4

    # Check 2: Runbook alignment (Remediation is grounded in retrieved content)
    if runbooks:
        runbook_content = runbooks[0].get("content", "")
        # Check if key tokens from runbook appear in remediation
        rb_words = set(runbook_content.lower().split())
        rem_words = set(remediation.lower().split())
        overlap = len(rb_words.intersection(rem_words))
        if overlap >= 3:
            score += 0.4
        elif overlap >= 1:
            score += 0.2
    else:
        score += 0.1

    # Check 3: Entity consistency (Service name matches state)
    service = state.get("service_name")
    if service and service.lower() in hypothesis.lower():
        score += 0.2

    groundedness = round(min(1.0, score), 2)

    if groundedness >= 0.75:
        verdict = "PASS"
    elif retry_count < 3:
        verdict = "REFINE"
        retry_count += 1
    else:
        verdict = "FAIL"

    msg = f"Self-RAG Groundedness check: {groundedness}/1.0 -> Verdict: {verdict} (Attempt {retry_count}/3)."
    return {
        "groundedness_score": groundedness,
        "critic_verdict": verdict,
        "retry_count": retry_count,
        "messages": [AIMessage(content=msg)]
    }
