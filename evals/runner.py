import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from omni_trace.agent import OmniTraceAgent
from evals.geval_judge import GEvalJudge

BENCHMARK_PATH = ROOT_DIR / "evals" / "benchmark_dataset.json"
RESULTS_DIR = ROOT_DIR / "eval_results"

def run_benchmarks() -> Dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    agent = OmniTraceAgent()
    judge = GEvalJudge()
    results = []

    print(f"\nRunning OmniTrace Benchmark Suite ({len(cases)} cases)...\n")

    total_start = time.time()
    correct_routing_count = 0
    geval_scores = []

    for idx, case in enumerate(cases, 1):
        print(f"[{idx}/{len(cases)}] {case['id']}: {case['name']}...")
        
        t0 = time.time()
        trace = agent.run(case["query"])
        elapsed = round(time.time() - t0, 2)

        tools_called = set(trace.tools_called)
        expected_tools = set(case["expected_tools"])
        routing_correct = expected_tools.issubset(tools_called)
        if routing_correct:
            correct_routing_count += 1

        # G-Eval semantic evaluation
        criteria = (
            "Evaluate whether the answer accurately answers the query, cites correct entities/metrics, "
            "and handles missing or unreleased data without hallucination."
        )
        geval_res = judge.evaluate(
            metric_name="Faithfulness & Hallucination Resistance",
            query=case["query"],
            actual_output=trace.final_answer,
            expected_facts=case["expected_facts"],
            description=case["description"],
            criteria=criteria
        )
        geval_scores.append(geval_res.score)

        record = {
            "id": case["id"],
            "name": case["name"],
            "category": case["category"],
            "routing_correct": routing_correct,
            "geval_score": round(geval_res.score, 2),
            "geval_reasoning": geval_res.reasoning,
            "latency_sec": elapsed,
            "tools_called": trace.tools_called
        }
        results.append(record)

    total_time = round(time.time() - total_start, 2)
    routing_pct = round((correct_routing_count / len(cases)) * 100, 1)
    avg_geval = round((sum(geval_scores) / len(geval_scores)), 2)
    avg_latency = round(total_time / len(cases), 2)

    report_data = {
        "summary": {
            "total_cases": len(cases),
            "routing_accuracy_pct": routing_pct,
            "avg_geval_score": avg_geval,
            "avg_latency_sec": avg_latency,
            "total_time_sec": total_time,
            "model": agent.model_name
        },
        "cases": results
    }

    report_md = generate_markdown_report(report_data)
    report_file = RESULTS_DIR / "benchmark_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\nBenchmark Complete -> {report_file}")
    print(f"Routing Accuracy: {routing_pct}% | Avg G-Eval Score: {avg_geval}/1.0 | Avg Latency: {avg_latency}s\n")

    return report_data

def generate_markdown_report(data: Dict[str, Any]) -> str:
    s = data["summary"]
    lines = [
        "# Benchmark Evaluation Report",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')} | **Model**: `{s['model']}`",
        "",
        "## Summary Metrics",
        "",
        f"- **Tool Routing Accuracy**: {s['routing_accuracy_pct']}%",
        f"- **Average G-Eval Quality Score**: {s['avg_geval_score']} / 1.0",
        f"- **Average Latency**: {s['avg_latency_sec']}s",
        f"- **Total Benchmark Duration**: {s['total_time_sec']}s",
        "",
        "## Detailed Results",
        "",
        "| ID | Test Case | Category | Routing | G-Eval | Latency |",
        "| :--- | :--- | :--- | :---: | :---: | :---: |"
    ]

    for c in data["cases"]:
        route = "[PASS]" if c["routing_correct"] else "[FAIL]"
        lines.append(
            f"| `{c['id']}` | {c['name']} | `{c['category']}` | {route} | {c['geval_score']} | {c['latency_sec']}s |"
        )

    return "\n".join(lines)

if __name__ == "__main__":
    run_benchmarks()
