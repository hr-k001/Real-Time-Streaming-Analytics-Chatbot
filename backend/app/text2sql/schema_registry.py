from __future__ import annotations

from typing import Any

from app.db.azure_sql import get_connection


SYSTEM_SCHEMAS = {"sys", "INFORMATION_SCHEMA"}


def load_database_schema() -> list[dict[str, Any]]:
    query = """
    SELECT
        TABLE_SCHEMA,
        TABLE_NAME,
        COLUMN_NAME,
        DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

    tables: dict[tuple[str, str], dict[str, Any]] = {}
    for schema_name, table_name, column_name, data_type in rows:
        if schema_name in SYSTEM_SCHEMAS:
            continue
        key = (schema_name, table_name)
        tables.setdefault(
            key,
            {"schema": schema_name, "table": table_name, "columns": []},
        )
        tables[key]["columns"].append({"name": column_name, "type": data_type})
    return list(tables.values())


def format_schema_for_prompt(schema: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for table in schema:
        columns = ", ".join(f"{col['name']} {col['type']}" for col in table["columns"])
        lines.append(f"{table['schema']}.{table['table']}({columns})")
    return "\n".join(lines)
