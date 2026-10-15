import pytest
from omni_trace.tools.sql_tool import SafeSQLTool, execute_sql
from omni_trace.safety.sql_guard import validate_sql_query
from omni_trace.agent import OmniTraceAgent

def test_sql_guardrail_blocks_drop_table():
    is_safe, error_msg, _ = validate_sql_query("DROP TABLE shows;")
    assert not is_safe
    assert "Permission denied" in error_msg or "Forbidden keyword" in error_msg

def test_sql_guardrail_blocks_destructive_updates():
    for destructive in [
        "UPDATE shows SET title='Hacked';",
        "DELETE FROM episodes WHERE episode_id=101;",
        "INSERT INTO shows VALUES (99, 'Fake', 'Comedy', 'Hindi', 1, 2025);"
    ]:
        is_safe, error_msg, _ = validate_sql_query(destructive)
        assert not is_safe, f"Failed to block: {destructive}"

def test_sql_guardrail_enforces_limit():
    is_safe, _, sanitized = validate_sql_query("SELECT * FROM episodes")
    assert is_safe
    assert "LIMIT 100" in sanitized

def test_operational_error_interception():
    result = execute_sql("SELECT dropoff_rate FROM retention_dropoffs;")
    assert not result["success"]
    assert "SQL OperationalError" in result["error"]
    assert "no such column: dropoff_rate" in result["error"]
    assert "tip" in result["metadata"]

def test_table_not_found_interception():
    result = execute_sql("SELECT * FROM non_existent_table;")
    assert not result["success"]
    assert "SQL OperationalError" in result["error"]
    assert "no such table" in result["error"]
