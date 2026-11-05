import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from omni_trace.graph.workflow import build_incident_graph
from omni_trace.database.vector_store import get_vector_store

@pytest.fixture(scope="module")
def graph():
    return build_incident_graph(enable_hitl=False)

def test_rag_triad_context_relevance():
    store = get_vector_store()
    results = store.search(query="504 Gateway Timeout checkout", service_name="checkout-service", top_k=2)
    assert len(results) >= 1
    top_rb = results[0]
    assert top_rb["service_name"] == "checkout-service"
    assert "504" in top_rb["title"] or "504" in top_rb["content"]

def test_rag_triad_groundedness(graph):
    res = graph.invoke(
        {"incident_query": "Checkout service returning 504 Gateway Timeout", "retry_count": 0, "messages": []},
        config={"configurable": {"thread_id": "test_grounded"}}
    )
    assert res["groundedness_score"] >= 0.75
    assert res["critic_verdict"] == "PASS"
    assert "504" in res["diagnostic_hypothesis"]

def test_rag_triad_answer_relevance(graph):
    res = graph.invoke(
        {"incident_query": "Auth service Redis connection pool exhausted", "retry_count": 0, "messages": []},
        config={"configurable": {"thread_id": "test_relevance"}}
    )
    assert "auth-service" in res["service_name"]
    assert "restart" in res["proposed_remediation"].lower() or "pool" in res["proposed_remediation"].lower()
    assert res["groundedness_score"] >= 0.75
