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


def test_summarizer_returns_numeric_stats():
    result = summarize_data([{"region": "North", "sales": 100}, {"region": "South", "sales": 200}])
    assert result["row_count"] == 2
    assert result["numeric_stats"]["sales"]["total"] == 300


def test_chart_generator_auto_bar_or_pie():
    result = generate_chart([{"region": "North", "sales": 100}, {"region": "South", "sales": 200}])
    assert "figure" in result
    assert result["chart_type"] in {"bar", "pie"}
