import sqlite3
from typing import Dict, Any
from langchain_core.messages import AIMessage
from omni_trace.graph.state import AgentState
from omni_trace.config import TELEMETRY_DB_PATH
from omni_trace.safety.sql_guard import validate_sql_query

def sql_analytics_node(state: AgentState) -> Dict[str, Any]:
    service = state.get("service_name")
    db_path = str(TELEMETRY_DB_PATH)

    base_query = """
    SELECT status_code, COUNT(*) as count, AVG(latency_ms) as avg_latency, MAX(latency_ms) as max_latency, error_message
    FROM service_telemetry_logs
    """
    if service:
        base_query += f" WHERE service_name = '{service}'"
    base_query += " GROUP BY status_code, error_message ORDER BY count DESC LIMIT 10"

    is_safe, err, sanitized = validate_sql_query(base_query)
    if not is_safe:
        return {
            "telemetry_summary": {"error": err},
            "messages": [AIMessage(content=f"Telemetry query blocked by guardrail: {err}")]
        }

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sanitized)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        error_rows = [r for r in rows if r.get("status_code", 200) >= 400]
        summary = {
            "service": service,
            "total_log_groups": len(rows),
            "error_events": error_rows,
            "raw_metrics": rows
        }

        msg = f"SQL telemetry analysis complete: {len(error_rows)} error pattern(s) identified for {service}."
        return {
            "telemetry_summary": summary,
            "messages": [AIMessage(content=msg)]
        }
    except Exception as exc:
        return {
            "telemetry_summary": {"error": str(exc)},
            "messages": [AIMessage(content=f"Telemetry execution failed: {exc}")]
        }
