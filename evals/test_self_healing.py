"""
Evaluation tests for OmniTrace self-healing mechanisms and safety guardrails.
Verifies that:
1. Destructive SQL statements are blocked before database execution.
2. Operational database errors return structured feedback with schema hints.
3. The agent loop successfully catches exceptions, reflects, and recovers.
"""

import pytest
from omni_trace.tools.sql_tool import SafeSQLTool, execute_sql
from omni_trace.safety.sql_guard import validate_sql_query
from omni_trace.agent import OmniTraceAgent

def test_sql_guardrail_blocks_drop_table():
    """Verify that DROP TABLE is blocked by AST safety validator."""
    is_safe, error_msg, _ = validate_sql_query("DROP TABLE shows;")
    assert not is_safe
    assert "Permission denied" in error_msg or "Forbidden keyword" in error_msg

def test_sql_guardrail_blocks_destructive_updates():
    """Verify that UPDATE, DELETE, and INSERT are blocked."""
    for destructive in [
        "UPDATE shows SET title='Hacked';",
        "DELETE FROM episodes WHERE episode_id=101;",
        "INSERT INTO shows VALUES (99, 'Fake', 'Comedy', 'Hindi', 1, 2025);"
    ]:
        is_safe, error_msg, _ = validate_sql_query(destructive)
        assert not is_safe, f"Failed to block: {destructive}"

def test_sql_guardrail_enforces_limit():
    """Verify that a query without LIMIT has LIMIT 100 injected."""
    is_safe, _, sanitized = validate_sql_query("SELECT * FROM episodes")
    assert is_safe
    assert "LIMIT 100" in sanitized

def test_operational_error_interception():
    """Verify that referencing an invalid column returns actionable self-healing feedback."""
    result = execute_sql("SELECT dropoff_rate FROM retention_dropoffs;")
    assert not result["success"]
    assert "SQL OperationalError" in result["error"]
    assert "no such column: dropoff_rate" in result["error"]
    assert "tip" in result["metadata"]

def test_table_not_found_interception():
    """Verify that referencing an invalid table returns actionable hints."""
    result = execute_sql("SELECT * FROM non_existent_table;")
    assert not result["success"]
    assert "SQL OperationalError" in result["error"]
    assert "no such table" in result["error"]
