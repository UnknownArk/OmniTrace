from omni_trace.graph.state import AgentState

def route_after_critic(state: AgentState) -> str:
    """
    Conditional routing edge evaluating Self-RAG groundedness score and safety gates.
    """
    verdict = state.get("critic_verdict", "FAIL")
    if verdict == "PASS":
        if state.get("is_sensitive_action", False) and not state.get("human_approved", False):
            return "human_approval_gate"
        return "report"
    elif verdict == "REFINE":
        return "refine_query"
    else:
        return "fallback"
