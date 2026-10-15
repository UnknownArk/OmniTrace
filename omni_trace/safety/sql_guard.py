import re
from typing import Tuple, Optional

FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "REPLACE", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "PRAGMA", "ATTACH", "DETACH", "VACUUM"
}

ALLOWED_STARTS = ("SELECT", "WITH")

class SQLGuardError(Exception):
    pass

def sanitize_query(query: str) -> str:
    cleaned = re.sub(r"--.*$", "", query, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    return cleaned.strip().rstrip(";")

def validate_sql_query(query: str, max_limit: int = 100) -> Tuple[bool, Optional[str], str]:
    """Validates query against read-only constraints and injects result limit."""
    if not query or not query.strip():
        return False, "Empty query provided.", ""

    cleaned = sanitize_query(query)
    tokens = re.findall(r"\b[A-Za-z_]+\b", cleaned)

    if not tokens:
        return False, "No valid SQL tokens found.", ""

    first_token = tokens[0].upper()
    if first_token not in ALLOWED_STARTS:
        return False, f"Permission denied: only SELECT/WITH allowed (got '{first_token}').", ""

    if ";" in cleaned:
        return False, "Security violation: stacked queries detected.", ""

    for token in tokens:
        upper = token.upper()
        if upper in FORBIDDEN_KEYWORDS:
            return False, f"Security violation: forbidden keyword '{upper}'.", ""

    if not re.search(r"\bLIMIT\s+\d+\b", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT {max_limit}"

    return True, None, cleaned
