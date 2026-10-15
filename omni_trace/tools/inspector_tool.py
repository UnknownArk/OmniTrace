"""
Database schema inspector tool.
Enables the agent to discover tables, column names, and data types on demand
rather than bloating the initial system prompt with complete schemas.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from omni_trace.config import DB_PATH
from omni_trace.models import ToolResult
from omni_trace.tools.base import BaseTool

class SchemaInspectorTool(BaseTool):
    """Tool to inspect relational database structure and table schemas."""

    name = "inspect_schema"
    description = (
        "Inspects available database tables or retrieves column definitions for a specific table. "
        "Use this first when you need to know which tables exist or what columns are available."
    )

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)

    def execute(self, table_name: Optional[str] = None) -> ToolResult:
        """
        If table_name is None, lists all tables in the database.
        If table_name is provided, describes columns and schema for that table.
        """
        try:
            # Connect in read-only mode via URI
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            if not table_name:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={"available_tables": tables},
                    row_count=len(tables),
                    is_empty=(len(tables) == 0)
                )

            # Describe specific table
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            conn.close()

            if not columns:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    is_empty=True,
                    error=f"Table '{table_name}' does not exist in the database.",
                    metadata={"suggested_action": "Call inspect_schema without arguments to see valid tables."}
                )

            schema_info = [
                {
                    "column_id": col[0],
                    "name": col[1],
                    "type": col[2],
                    "not_null": bool(col[3]),
                    "primary_key": bool(col[5])
                }
                for col in columns
            ]

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"table": table_name, "columns": schema_info},
                row_count=len(schema_info),
                is_empty=False
            )

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Database inspection error: {str(e)}"
            )

def inspect_schema(table_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspects available database tables or retrieves column definitions for a specific table.
    
    Args:
        table_name: The name of the table to inspect. Leave empty/None to list all tables.
    """
    tool = SchemaInspectorTool()
    return tool.execute(table_name=table_name).model_dump()
