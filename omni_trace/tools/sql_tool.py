import sqlite3
from typing import Dict, Any, Optional
from omni_trace.config import DB_PATH
from omni_trace.models import ToolResult
from omni_trace.tools.base import BaseTool
from omni_trace.safety.sql_guard import validate_sql_query

class SafeSQLTool(BaseTool):
    name = "execute_sql"
    description = (
        "Executes a read-only SQL query against the SQLite telemetry database. "
        "Only SELECT or WITH queries are permitted. Returns rows as structured JSON."
    )

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)

    def execute(self, query: str) -> ToolResult:
        is_safe, guard_error, sanitized_query = validate_sql_query(query)
        if not is_safe:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Guardrail Block: {guard_error}",
                metadata={"action": "Rewrite query following read-only constraints."}
            )

        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(sanitized_query)
            rows = cursor.fetchall()
            conn.close()

            dict_rows = [dict(r) for r in rows]
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=dict_rows,
                row_count=len(dict_rows),
                is_empty=(len(dict_rows) == 0),
                metadata={"query_executed": sanitized_query}
            )

        except sqlite3.OperationalError as e:
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
                error=f"Database execution error: {str(e)}"
            )

def execute_sql(query: str) -> Dict[str, Any]:
    tool = SafeSQLTool()
    return tool.execute(query=query).model_dump()
