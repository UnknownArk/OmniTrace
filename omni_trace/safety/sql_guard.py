"""
SQL safety guardrail and AST validator.
Ensures that all autonomous LLM-generated SQL queries are strictly read-only,
contain no destructive statements, and enforce result limits.
"""

import re
from typing import Tuple, Optional

FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "REPLACE", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "PRAGMA", "ATTACH", "DETACH", "VACUUM"
}

ALLOWED_STARTS = ("SELECT", "WITH")

class SQLGuardError(Exception):
    """Raised when an SQL query violates safety constraints."""
    pass

def sanitize_query(query: str) -> str:
    """Removes trailing semicolons, leading/trailing whitespace, and inline comments."""
    # Strip SQL single line comments (-- ...)
    cleaned = re.sub(r"--.*$", "", query, flags=re.MULTILINE)
    # Strip SQL block comments (/* ... */)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    # Strip whitespace and trailing semicolons
    cleaned = cleaned.strip().rstrip(";")
    return cleaned

def validate_sql_query(query: str, max_limit: int = 100) -> Tuple[bool, Optional[str], str]:
    """
    Validates that a query is safe for execution.
    Returns:
        (is_valid: bool, error_message: Optional[str], sanitized_query: str)
    """
    if not query or not query.strip():
        return False, "Empty query provided.", ""

    cleaned = sanitize_query(query)
    tokens = re.findall(r"\b[A-Za-z_]+\b", cleaned)

    if not tokens:
        return False, "No valid SQL tokens found.", ""

    # 1. Enforce that query starts with SELECT or WITH
    first_token = tokens[0].upper()
    if first_token not in ALLOWED_STARTS:
        return False, f"Permission denied: Only read-only queries starting with SELECT or WITH are permitted. Found: {first_token}", ""

    # 2. Guard against multiple statements (stacked queries via semicolon)
    if ";" in cleaned:
        return False, "Security violation: Multiple statements / query chaining detected.", ""

    # 3. Check for forbidden keywords anywhere in the query
    for token in tokens:
        upper_token = token.upper()
        if upper_token in FORBIDDEN_KEYWORDS:
            return False, f"Security violation: Forbidden keyword '{upper_token}' detected in query.", ""

    # 4. Inject or verify LIMIT clause to prevent out-of-memory dumps
    if not re.search(r"\bLIMIT\s+\d+\b", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT {max_limit}"

    return True, None, cleaned
