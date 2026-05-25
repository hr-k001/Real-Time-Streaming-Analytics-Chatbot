import re

from app.core.config import settings
from app.core.exceptions import QueryValidationError


FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|merge|exec|execute|create|grant|revoke)\b",
    re.IGNORECASE,
)


def validate_select_query(sql: str) -> str:
    cleaned = sql.strip().rstrip(";")
    lowered = cleaned.lower()

    if not lowered.startswith("select"):
        raise QueryValidationError("Only SELECT queries are allowed.")
    if ";" in cleaned:
        raise QueryValidationError("Multiple SQL statements are not allowed.")
    if FORBIDDEN_SQL.search(cleaned):
        raise QueryValidationError("Query contains a forbidden SQL operation.")

    if " top " not in f" {lowered} " and " count(" not in lowered:
        cleaned = re.sub(r"^select\s+", f"SELECT TOP {settings.SQL_MAX_ROWS} ", cleaned, flags=re.IGNORECASE)

    return cleaned
