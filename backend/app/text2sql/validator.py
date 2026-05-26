from app.text2sql.query_validator import validate_query


def validate_select_query(sql: str) -> str:
    """Compatibility wrapper for the stronger Binit query validator."""
    return validate_query(sql)
