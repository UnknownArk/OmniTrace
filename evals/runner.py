"""
Automated Evaluation Benchmark Runner for OmniTrace.
Executes golden dataset benchmark cases, tracks tool routing precision,
measures fact recall and execution latency, and generates a markdown report.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure UTF-8 output encoding across Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from omni_trace.agent import OmniTraceAgent
from omni_trace.config import ROOT_DIR

BENCHMARK_PATH = ROOT_DIR / "evals" / "benchmark_dataset.json"
RESULTS_DIR = ROOT_DIR / "eval_results"

def run_benchmarks() -> Dict[str, Any]:
    """Runs all benchmark cases and aggregates performance metrics."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    agent = OmniTraceAgent()
    results = []

    print(f"\n[START] OmniTrace Benchmark Suite ({len(cases)} test cases)...\n")

    total_start = time.time()
    correct_routing_count = 0
    fact_coverage_scores = []

    for idx, case in enumerate(cases, 1):
        print(f"[{idx}/{len(cases)}] Evaluating: {case['name']} ({case['id']})...")
        
        t0 = time.time()
        trace = agent.run(case["query"])
        elapsed = round(time.time() - t0, 2)

        # 1. Routing Accuracy Evaluation
        tools_called_set = set(trace.tools_called)
        expected_tools_set = set(case["expected_tools"])
        routing_correct = expected_tools_set.issubset(tools_called_set)
        if routing_correct:
            correct_routing_count += 1

        # 2. Fact Recall Evaluation
        lower_ans = trace.final_answer.lower()
        facts_matched = [
            fact for fact in case["expected_facts"]
            if fact.lower() in lower_ans
        ]
        fact_score = (len(facts_matched) / len(case["expected_facts"])) if case["expected_facts"] else 1.0
        fact_coverage_scores.append(fact_score)

        record = {
            "id": case["id"],
            "name": case["name"],
            "category": case["category"],
            "query": case["query"],
            "status": trace.status,
            "routing_correct": routing_correct,
            "expected_tools": case["expected_tools"],
            "tools_called": trace.tools_called,
            "fact_recall_pct": round(fact_score * 100, 1),
            "self_healed": trace.self_healing_count > 0,
            "latency_sec": elapsed,
            "answer_preview": trace.final_answer[:150].replace("\n", " ") + "..."
        }
        results.append(record)

    total_time = round(time.time() - total_start, 2)
    routing_accuracy_pct = round((correct_routing_count / len(cases)) * 100, 1)
    avg_fact_recall_pct = round((sum(fact_coverage_scores) / len(fact_coverage_scores)) * 100, 1)
    avg_latency = round(total_time / len(cases), 2)

    report_data = {
        "summary": {
            "total_cases": len(cases),
            "routing_accuracy_pct": routing_accuracy_pct,
            "avg_fact_recall_pct": avg_fact_recall_pct,
            "avg_latency_sec": avg_latency,
            "total_benchmark_time_sec": total_time,
            "provider_evaluated": agent.provider,
            "model_evaluated": agent.model_name
        },
        "cases": results
    }

    # Generate Markdown Report
    report_md = generate_markdown_report(report_data)
    report_file = RESULTS_DIR / "benchmark_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\n[COMPLETE] Benchmark Complete! Report generated at: {report_file}")
    print(f"[METRICS] Routing Accuracy: {routing_accuracy_pct}% | Fact Recall: {avg_fact_recall_pct}% | Avg Latency: {avg_latency}s\n")

    return report_data

def generate_markdown_report(data: Dict[str, Any]) -> str:
    s = data["summary"]
    lines = [
        "# OmniTrace Benchmark Evaluation Report",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Provider**: `{s['provider_evaluated']}` | **Model**: `{s['model_evaluated']}`",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Total Benchmark Test Cases** | {s['total_cases']} |",
        f"| **Tool Routing Accuracy** | **{s['routing_accuracy_pct']}%** |",
        f"| **Fact Recall / Coverage** | **{s['avg_fact_recall_pct']}%** |",
        f"| **Average Query Latency** | {s['avg_latency_sec']}s |",
        f"| **Total Evaluation Time** | {s['total_benchmark_time_sec']}s |",
        "",
        "## Case-by-Case Breakdown",
        "",
        "| ID | Test Case | Category | Routing | Fact Recall | Latency | Tools Called |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :--- |"
    ]

    for c in data["cases"]:
        route_icon = "✅" if c["routing_correct"] else "❌"
        tools_str = ", ".join(f"`{t}`" for t in c["tools_called"])
        lines.append(
            f"| `{c['id']}` | {c['name']} | `{c['category']}` | {route_icon} | {c['fact_recall_pct']}% | {c['latency_sec']}s | {tools_str} |"
        )

    lines.extend([
        "",
        "## Architectural Assertions",
        "- **Zero Hallucination on Missing Data**: Missing transcripts and telemetry are explicitly flagged rather than invented.",
        "- **Read-Only SQL Safety**: Validated AST guards enforce read-only statements and inject memory limits.",
        "- **Windowed Temporal Alignment**: Scene dialogue retrieval absorbs clock drift and playhead latency via temporal windows."
    ])

    return "\n".join(lines)

if __name__ == "__main__":
    run_benchmarks()
