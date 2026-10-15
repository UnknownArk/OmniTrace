"""
Evaluation tests for OmniTrace tool routing accuracy and execution validity.
Uses pytest to deterministically benchmark the agent against golden test cases.
"""

import sys
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from omni_trace.agent import OmniTraceAgent

BENCHMARK_PATH = ROOT_DIR / "evals" / "benchmark_dataset.json"

@pytest.fixture(scope="module")
def benchmark_data():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def agent():
    return OmniTraceAgent()

def test_hybrid_correlation_routing(agent, benchmark_data):
    """Test 01: Verify agent calls both SQL and RAG for a hybrid drop-off question."""
    case = next(c for c in benchmark_data if c["id"] == "hybrid_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED", f"Agent failed with status {trace.status}"
    
    # Assert both SQL and RAG tools were invoked
    assert "execute_sql" in trace.tools_called, "Agent failed to invoke execute_sql for telemetry"
    assert "search_transcripts" in trace.tools_called, "Agent failed to invoke search_transcripts for scene script"

    # Assert critical ground truth facts are present in final answer
    lower_answer = trace.final_answer.lower()
    assert "103" in lower_answer or "the ambush" in lower_answer, "Missing episode identifier"
    assert "38.4" in lower_answer or "38" in lower_answer, "Missing drop-off metric"

def test_sql_only_routing(agent, benchmark_data):
    """Test 02: Verify agent calls only SQL for pure quantitative telemetry."""
    case = next(c for c in benchmark_data if c["id"] == "sql_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "execute_sql" in trace.tools_called
    # Shouldn't invoke transcripts for purely numerical regional queries
    assert "search_transcripts" not in trace.tools_called

    lower_answer = trace.final_answer.lower()
    assert "54" in lower_answer, "Missing Haryana viewer share (54%)"

def test_rag_only_routing(agent, benchmark_data):
    """Test 03: Verify agent calls only RAG for narrative dialogue questions."""
    case = next(c for c in benchmark_data if c["id"] == "rag_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "search_transcripts" in trace.tools_called

    lower_answer = trace.final_answer.lower()
    assert any(term in lower_answer for term in ["consignment", "police", "bypass", "toll"]), (
        "Final answer did not capture Murthal toll scene details"
    )

def test_missing_transcript_graceful_handling(agent, benchmark_data):
    """Test 04: Edge case where SQL data exists but transcript is missing."""
    case = next(c for c in benchmark_data if c["id"] == "missing_rag_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "execute_sql" in trace.tools_called

    lower_answer = trace.final_answer.lower()
    # Must cite the drop-off rate and acknowledge missing transcript or non-dialogue
    assert "41" in lower_answer or "41.2" in lower_answer
    assert any(term in lower_answer for term in ["missing", "no dialogue", "no transcript", "silent", "not found"]), (
        "Agent failed to report missing transcript record"
    )
