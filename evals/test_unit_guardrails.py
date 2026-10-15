"""
Deterministic Unit Tests for OmniTrace tool primitives and safety guardrails.
Runs entirely offline without requiring external LLM API calls for fast CI/CD execution.
"""

import sys
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from omni_trace.safety.sql_guard import validate_sql_query
from omni_trace.tools.sql_tool import SafeSQLTool
from omni_trace.tools.rag_tool import TranscriptRAGTool
from omni_trace.tools.inspector_tool import SchemaInspectorTool

def test_sql_guard_valid_select():
    """Verify valid SELECT queries pass with injected LIMIT."""
    is_safe, err, query = validate_sql_query("SELECT show_id, title FROM shows;")
    assert is_safe
    assert err is None
    assert "LIMIT 100" in query

def test_sql_guard_valid_with_cte():
    """Verify valid CTE queries starting with WITH pass."""
    cte = "WITH ranked AS (SELECT * FROM episodes) SELECT * FROM ranked"
    is_safe, err, query = validate_sql_query(cte)
    assert is_safe
    assert err is None

def test_sql_guard_blocks_destructive_keywords():
    """Verify all destructive SQL operations are strictly blocked."""
    forbidden = [
        "DROP TABLE shows;",
        "DELETE FROM episodes WHERE episode_id=101;",
        "UPDATE shows SET title='hacked';",
        "INSERT INTO shows VALUES (99, 'bad', 'bad', 'bad', 1, 2025);",
        "ALTER TABLE shows ADD COLUMN hacked TEXT;",
        "TRUNCATE TABLE shows;",
        "ATTACH DATABASE 'other.db' AS other;"
    ]
    for q in forbidden:
        is_safe, err, _ = validate_sql_query(q)
        assert not is_safe, f"Failed to block dangerous query: {q}"
        assert err is not None

def test_sql_guard_blocks_stacked_queries():
    """Verify multiple statements chained by semicolons are blocked."""
    chained = "SELECT * FROM shows; DROP TABLE episodes;"
    is_safe, err, _ = validate_sql_query(chained)
    assert not is_safe
    assert "Multiple statements" in err

def test_schema_inspector_lists_tables():
    """Verify SchemaInspectorTool discovers existing SQLite tables."""
    inspector = SchemaInspectorTool()
    res = inspector.execute()
    assert res.success
    tables = res.data["available_tables"]
    assert "shows" in tables
    assert "episodes" in tables
    assert "retention_dropoffs" in tables

def test_safe_sql_tool_execution():
    """Verify SafeSQLTool executes a read-only query and returns dict rows."""
    tool = SafeSQLTool()
    res = tool.execute("SELECT * FROM shows ORDER BY show_id;")
    assert res.success
    assert res.row_count > 0
    assert res.data[0]["title"] == "Bhaichara"

def test_safe_sql_tool_catches_invalid_column():
    """Verify SafeSQLTool catches operational errors and returns actionable metadata."""
    tool = SafeSQLTool()
    res = tool.execute("SELECT fake_col FROM shows;")
    assert not res.success
    assert "SQL OperationalError" in res.error
    assert "tip" in res.metadata

def test_rag_tool_windowed_retrieval():
    """Verify TranscriptRAGTool finds scenes within the temporal window."""
    rag = TranscriptRAGTool()
    # Scene 4 in Ep 103 spans [760s - 885s]. Query centered at 790s (+/-60s).
    res = rag.execute(episode_id=103, timestamp_seconds=790, window_seconds=60)
    assert res.success
    assert res.row_count >= 1
    assert res.data[0]["episode_id"] == 103
    assert "Abandoned Warehouse" in res.data[0]["location"]

def test_rag_tool_missing_episode():
    """Verify TranscriptRAGTool reports empty gracefully for non-existent episode."""
    rag = TranscriptRAGTool()
    res = rag.execute(episode_id=999)
    assert res.success
    assert res.is_empty
    assert res.row_count == 0
