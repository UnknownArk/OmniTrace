"""
Tool registry and exports for OmniTrace agent.
"""

from omni_trace.tools.inspector_tool import inspect_schema, SchemaInspectorTool
from omni_trace.tools.sql_tool import execute_sql, SafeSQLTool
from omni_trace.tools.rag_tool import search_transcripts, TranscriptRAGTool

ALL_TOOLS = [inspect_schema, execute_sql, search_transcripts]

__all__ = [
    "inspect_schema",
    "execute_sql",
    "search_transcripts",
    "SchemaInspectorTool",
    "SafeSQLTool",
    "TranscriptRAGTool",
    "ALL_TOOLS",
]
