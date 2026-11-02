from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState

def report_node(state: AgentState) -> Dict[str, Any]:
    service = state.get("service_name", "Unknown")
    hypothesis = state.get("diagnostic_hypothesis", "")
    remediation = state.get("proposed_remediation", "")
    groundedness = state.get("groundedness_score", 0.0)
    retry_count = state.get("retry_count", 0)
    is_sensitive = state.get("is_sensitive_action", False)
    approved = state.get("human_approved", False)

    status_str = "APPROVED & EXECUTABLE" if approved or not is_sensitive else "PENDING HUMAN APPROVAL"

    report = f"""
============================================================
OMNITRACE SRE INCIDENT TRIAGE REPORT
============================================================
Target Service      : {service}
Groundedness Score  : {groundedness:.2f} / 1.0 (Self-RAG Verified)
Refinement Cycles   : {retry_count}
Remediation Status  : {status_str}

DIAGNOSIS:
{hypothesis}

RECOMMENDED ACTION:
{remediation}
============================================================
""".strip()

    return {
        "final_report": report,
        "messages": [AIMessage(content="Final incident report compiled.")]
    }

def fallback_node(state: AgentState) -> Dict[str, Any]:
    service = state.get("service_name", "Unknown")
    report = f"""
============================================================
OMNITRACE SRE INCIDENT TRIAGE REPORT (FALLBACK)
============================================================
Target Service      : {service}
Status              : REFINEMENT BUDGET EXHAUSTED (>3 attempts)
Recommendation      : Escalate to Level 3 On-Call SRE. Telemetry and Runbooks could not be reconciled with >0.75 confidence.
============================================================
""".strip()

    return {
        "final_report": report,
        "messages": [AIMessage(content="Refinement budget exhausted. Fallback report generated.")]
    }
