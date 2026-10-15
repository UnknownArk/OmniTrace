"""
Safe SQL Query Executor tool with read-only connection locks,
guardrail enforcement, and rich error tracebacks for autonomous self-healing.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from omni_trace.config import DB_PATH
from omni_trace.models import ToolResult
from omni_trace.tools.base import BaseTool
from omni_trace.safety.sql_guard import validate_sql_query

class SafeSQLTool(BaseTool):
    """Tool to execute read-only SQL queries against the relational database."""

    name = "execute_sql"
    description = (
        "Executes a safe, read-only SQL query against the SQLite telemetry database. "
        "Only SELECT or WITH queries are permitted. Destructive queries (DROP, INSERT, etc.) are blocked. "
        "Returns rows as structured JSON."
    )

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)

    def execute(self, query: str) -> ToolResult:
        """Executes the provided SQL query with guardrail checks and read-only locks."""
        # 1. Guardrail validation
        is_safe, guard_error, sanitized_query = validate_sql_query(query)
        if not is_safe:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Guardrail Block: {guard_error}",
                metadata={"action": "Rewrite query following read-only constraints."}
            )

        # 2. Execute via Read-Only SQLite Connection
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row  # Return dict-like rows
            cursor = conn.cursor()

            cursor.execute(sanitized_query)
            rows = cursor.fetchall()
            conn.close()

            dict_rows = [dict(row) for row in rows]
            row_count = len(dict_rows)

            if row_count == 0:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[],
                    row_count=0,
                    is_empty=True,
                    metadata={
                        "query_executed": sanitized_query,
                        "message": "Query executed successfully, but returned 0 matching rows."
                    }
                )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data=dict_rows,
                row_count=row_count,
                is_empty=False,
                metadata={"query_executed": sanitized_query}
            )

        except sqlite3.OperationalError as e:
            # Self-healing feedback: Return exact SQLite error and hint
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"SQL OperationalError: {str(e)}",
                metadata={
                    "failed_query": sanitized_query,
                    "tip": "Check table and column names via inspect_schema if a column or table was missing."
                }
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unexpected database execution error: {str(e)}"
            )

def execute_sql(query: str) -> Dict[str, Any]:
    """
    Executes a safe, read-only SQL query against the telemetry database.
    
    Args:
        query: The SQL query to execute (must start with SELECT or WITH).
    """
    tool = SafeSQLTool()
    return tool.execute(query=query).model_dump()
