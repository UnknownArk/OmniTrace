"""
Security and safety guardrails for OmniTrace autonomous execution.
"""
from omni_trace.safety.sql_guard import validate_sql_query, SQLGuardError

__all__ = ["validate_sql_query", "SQLGuardError"]
