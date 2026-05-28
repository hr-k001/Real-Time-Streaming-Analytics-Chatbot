from app.text2sql.validator import validate_select_query
from app.tools.chart_generator import generate_chart
from app.tools.data_summarizer import summarize_data


def test_validate_select_blocks_mutation():
    try:
        validate_select_query("DROP TABLE dbo.orders")
    except Exception as exc:
        assert "Only SELECT" in str(exc) or "forbidden" in str(exc)
    else:
        raise AssertionError("Mutation query was not blocked")


def test_validate_select_adds_top():
    sql = validate_select_query("SELECT region_name FROM dbo.regions")
    assert "TOP" in sql


def test_validate_select_allows_cte():
    sql = validate_select_query(
        "WITH recent_orders AS (SELECT TOP 10 order_id FROM dbo.orders) SELECT * FROM recent_orders"
    )
    assert sql.startswith("WITH")


def test_summarizer_returns_numeric_stats():
    result = summarize_data([{"region": "North", "sales": 100}, {"region": "South", "sales": 200}])
    assert result["row_count"] == 2
    assert result["numeric_stats"]["sales"]["total"] == 300


def test_chart_generator_auto_bar_or_pie():
    result = generate_chart([{"region": "North", "sales": 100}, {"region": "South", "sales": 200}])
    assert "figure" in result
    assert result["chart_type"] in {"bar", "pie"}


def test_chart_generator_accepts_sql_result_object():
    result = generate_chart(
        {
            "columns": ["product_name", "price"],
            "rows": [
                {"product_name": "Analytics Pro", "price": 199},
                {"product_name": "Dashboard Add-on", "price": 79},
            ],
        },
        x="product_name",
        y="price",
    )
    assert "figure" in result
    trace = result["figure"]["data"][0]
    assert trace["labels"] == ["Analytics Pro", "Dashboard Add-on"]
    assert trace["values"] == [199, 79]


def test_chart_generator_accepts_column_row_arrays():
    result = generate_chart(
        {
            "columns": ["product_name", "price"],
            "rows": [["Analytics Pro", 199], ["Dashboard Add-on", 79]],
        },
        x="product_name",
        y="price",
    )
    assert "figure" in result
    trace = result["figure"]["data"][0]
    assert trace["labels"] == ["Analytics Pro", "Dashboard Add-on"]
    assert trace["values"] == [199, 79]


def test_sql_executor_uses_enhanced_cache(monkeypatch):
    from app.cache.enhanced_query_cache import get_cached_result, invalidate_all
    from app.tools import sql_executor

    invalidate_all()
    calls = {"count": 0}

    def fake_execute_select(sql):
        calls["count"] += 1
        return {"columns": ["id"], "rows": [{"id": 1}], "row_count": 1, "truncated": False}

    monkeypatch.setattr(sql_executor, "execute_select", fake_execute_select)
    sql = "SELECT id FROM dbo.cache_test"

    first = sql_executor.run_sql_executor(sql)
    second = sql_executor.run_sql_executor(sql)

    assert first["from_cache"] is False
    assert second["from_cache"] is True
    assert calls["count"] == 1
    assert get_cached_result(first["sql"]) is not None
