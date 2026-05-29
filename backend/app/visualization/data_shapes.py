from typing import Any


def coerce_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        if all(isinstance(row, dict) for row in data):
            return data
        return []

    if isinstance(data, dict):
        rows = data.get("rows") or data.get("data") or data.get("result")
        columns = data.get("columns")
        if isinstance(rows, list):
            if all(isinstance(row, dict) for row in rows):
                return rows
            if isinstance(columns, list):
                converted = []
                for row in rows:
                    if isinstance(row, list | tuple):
                        converted.append(dict(zip(columns, row)))
                return converted

        if data and all(not isinstance(value, (list, dict)) for value in data.values()):
            return [data]

    return []
