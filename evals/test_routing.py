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
    case = next(c for c in benchmark_data if c["id"] == "hybrid_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "execute_sql" in trace.tools_called
    assert "search_transcripts" in trace.tools_called

    ans = trace.final_answer.lower()
    assert "103" in ans or "ambush" in ans
    assert "38.4" in ans or "38" in ans

def test_sql_only_routing(agent, benchmark_data):
    case = next(c for c in benchmark_data if c["id"] == "sql_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "execute_sql" in trace.tools_called
    assert "search_transcripts" not in trace.tools_called
    assert "54" in trace.final_answer.lower()

def test_rag_only_routing(agent, benchmark_data):
    case = next(c for c in benchmark_data if c["id"] == "rag_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "search_transcripts" in trace.tools_called
    ans = trace.final_answer.lower()
    assert any(w in ans for w in ["consignment", "police", "bypass", "toll"])

def test_missing_transcript_handling(agent, benchmark_data):
    case = next(c for c in benchmark_data if c["id"] == "missing_rag_01")
    trace = agent.run(case["query"])

    assert trace.status == "COMPLETED"
    assert "execute_sql" in trace.tools_called
    ans = trace.final_answer.lower()
    assert "41" in ans or "41.2" in ans
    assert any(w in ans for w in ["missing", "no dialogue", "no transcript", "silent", "not found", "absent"])
