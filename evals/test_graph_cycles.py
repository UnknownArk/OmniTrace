import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from omni_trace.graph.workflow import build_incident_graph
from omni_trace.graph.nodes.critic import critic_node

def test_graph_hitl_interruption():
    graph = build_incident_graph(enable_hitl=True)
    config = {"configurable": {"thread_id": "test_hitl_cycle"}}

    graph.invoke(
        {"incident_query": "Checkout service 504 error", "retry_count": 0, "messages": []},
        config=config
    )
    state = graph.get_state(config)
    assert state.next == ("human_approval_gate",)

    res = graph.invoke(None, config=config)
    assert res["human_approved"] is True
    assert "OMNITRACE SRE INCIDENT TRIAGE REPORT" in res["final_report"]

def test_critic_cyclical_refinement():
    hallucinated_state = {
        "diagnostic_hypothesis": "The moon is made of green cheese and alien servers crashed.",
        "proposed_remediation": "Do nothing.",
        "telemetry_summary": {"error_events": []},
        "retrieved_runbooks": [],
        "retry_count": 0,
        "service_name": "checkout-service"
    }
    critic_res = critic_node(hallucinated_state)
    assert critic_res["critic_verdict"] == "REFINE"
    assert critic_res["groundedness_score"] < 0.75
    assert critic_res["retry_count"] == 1

def test_circuit_breaker_budget_exhaustion():
    exhausted_state = {
        "diagnostic_hypothesis": "Fabricated root cause without telemetry evidence.",
        "proposed_remediation": "Generic advice.",
        "telemetry_summary": {"error_events": []},
        "retrieved_runbooks": [],
        "retry_count": 3,
        "service_name": "unknown-service"
    }
    critic_res = critic_node(exhausted_state)
    assert critic_res["critic_verdict"] == "FAIL"
