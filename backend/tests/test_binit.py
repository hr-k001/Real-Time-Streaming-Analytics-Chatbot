"""
tests/test_binit.py
--------------------
Unit tests for Binit's user stories US-08 to US-16.
Run with: pytest tests/test_binit.py -v
"""
import pytest


# ── US-08: Text2SQL Pipeline ──────────────────────────────────────────────────

def test_text2sql_sql_extraction():
    """_extract_sql should strip markdown fences."""
    from app.text2sql.text2sql_pipeline import Text2SQLPipeline
    pipeline = Text2SQLPipeline()
    raw = "```sql\nSELECT TOP 10 * FROM dbo.orders\n```"
    result = pipeline._extract_sql(raw)
    assert result == "SELECT TOP 10 * FROM dbo.orders"


def test_text2sql_extract_plain_select():
    from app.text2sql.text2sql_pipeline import Text2SQLPipeline
    pipeline = Text2SQLPipeline()
    raw = "Here is your query:\nSELECT region FROM dbo.regions"
    result = pipeline._extract_sql(raw)
    assert result.startswith("SELECT")


# ── US-09: Query Validation ───────────────────────────────────────────────────

def test_validator_blocks_drop():
    from app.text2sql.query_validator import validate_query_report
    report = validate_query_report("DROP TABLE dbo.orders")
    assert not report["is_valid"]
    assert any("SELECT" in e or "forbidden" in e.lower() for e in report["errors"])


def test_validator_blocks_injection():
    from app.text2sql.query_validator import validate_query_report
    report = validate_query_report("SELECT * FROM dbo.orders; DROP TABLE dbo.orders")
    assert not report["is_valid"]


def test_validator_blocks_hex():
    from app.text2sql.query_validator import validate_query_report
    report = validate_query_report("SELECT 0xDEADBEEF FROM dbo.orders")
    assert not report["is_valid"]


def test_validator_passes_clean_select():
    from app.text2sql.query_validator import validate_query_report
    report = validate_query_report("SELECT region, SUM(revenue) FROM dbo.sales GROUP BY region")
    assert report["is_valid"]


def test_validator_adds_top():
    from app.text2sql.query_validator import validate_query_report
    report = validate_query_report("SELECT region FROM dbo.regions")
    assert "TOP" in report["sql"]


def test_validator_warns_on_comments():
    from app.text2sql.query_validator import validate_query_report
    report = validate_query_report("SELECT * FROM dbo.orders -- where region='North'")
    # Should still be valid but with a warning
    assert report["is_valid"]
    assert any("comment" in w.lower() for w in report["warnings"])


# ── US-10: Advanced SQL ───────────────────────────────────────────────────────

def test_date_filter_last_7_days():
    from app.text2sql.advanced_sql import build_date_filter
    fragment = build_date_filter("order_date", "last_7_days")
    assert "DATEADD" in fragment
    assert "order_date" in fragment


def test_date_filter_unknown_window():
    from app.text2sql.advanced_sql import build_date_filter
    with pytest.raises(ValueError, match="Unknown date window"):
        build_date_filter("order_date", "last_century")


def test_aggregation_query_builds_correctly():
    from app.text2sql.advanced_sql import build_aggregation_query
    sql = build_aggregation_query(
        table="dbo.sales",
        metric_col="revenue",
        agg_func="SUM",
        group_by_cols=["region"],
        top_n=50,
    )
    assert "SUM(revenue)" in sql
    assert "GROUP BY region" in sql
    assert "TOP 50" in sql


def test_aggregation_count_distinct():
    from app.text2sql.advanced_sql import build_aggregation_query
    sql = build_aggregation_query(
        table="dbo.orders",
        metric_col="customer_id",
        agg_func="COUNT_DISTINCT",
        group_by_cols=["region"],
    )
    assert "COUNT(DISTINCT customer_id)" in sql


def test_run_advanced_sql_unknown_mode():
    from app.text2sql.advanced_sql import run_advanced_sql
    result = run_advanced_sql(mode="unknown_mode")
    assert "error" in result


def test_run_advanced_sql_join_mode():
    from app.text2sql.advanced_sql import run_advanced_sql
    result = run_advanced_sql(
        mode="join",
        table="dbo.orders o",
        joins=[{"type": "INNER", "table": "dbo.customers c", "on": "o.customer_id = c.customer_id"}],
        select_cols=["o.order_id", "c.customer_name"],
    )
    assert "error" not in result
    assert "JOIN dbo.customers c" in result["sql"]


def test_cte_query_validates():
    from app.text2sql.advanced_sql import build_cte_query
    sql = build_cte_query(
        cte_name="recent_orders",
        cte_body="SELECT TOP 10 order_id, customer_id FROM dbo.orders",
        outer_query="SELECT * FROM recent_orders",
    )
    assert sql.startswith("WITH recent_orders")


# ── US-11: Dynamic Chart Selection ───────────────────────────────────────────

def test_chart_selection_temporal_x():
    from app.visualization.dynamic_chart import select_chart_type
    rows = [{"sale_date": "2024-01", "revenue": 1000}]
    chart = select_chart_type(rows, question="", x_col="sale_date")
    assert chart == "line"


def test_chart_selection_few_categories():
    from app.visualization.dynamic_chart import select_chart_type
    rows = [{"region": r, "revenue": i * 100} for i, r in enumerate(["North", "South", "East"])]
    chart = select_chart_type(rows, question="", x_col="region")
    assert chart == "pie"


def test_chart_selection_question_keyword():
    from app.visualization.dynamic_chart import select_chart_type
    rows = [{"product": "A", "sales": 100}] * 10
    chart = select_chart_type(rows, question="Show me the distribution of sales", x_col="product")
    assert chart == "histogram"


def test_smart_chart_returns_figure():
    from app.visualization.dynamic_chart import smart_chart
    rows = [{"region": "North", "revenue": 100}, {"region": "South", "revenue": 200}]
    result = smart_chart(rows, question="show me a bar chart")
    assert "figure" in result
    assert "chart_type" in result


def test_smart_chart_empty_data():
    from app.visualization.dynamic_chart import smart_chart
    result = smart_chart([])
    assert "error" in result


# ── US-12: Plotly Visualization Integration ───────────────────────────────────

def test_apply_theme_dark_mode():
    from app.visualization.plotly_integration import apply_theme
    figure = {"data": [], "layout": {}}
    themed = apply_theme(figure, palette="blue", dark_mode=True)
    assert themed["layout"]["paper_bgcolor"] == "#1e1e2e"


def test_apply_theme_colorway():
    from app.visualization.plotly_integration import apply_theme, PALETTES
    figure = {"data": [], "layout": {}}
    themed = apply_theme(figure, palette="warm")
    assert themed["layout"]["colorway"] == PALETTES["warm"]


def test_build_multi_series_figure():
    from app.visualization.plotly_integration import build_multi_series_figure
    rows = [
        {"month": "Jan", "revenue": 100, "profit": 40},
        {"month": "Feb", "revenue": 150, "profit": 60},
    ]
    fig = build_multi_series_figure(rows, x_col="month", y_cols=["revenue", "profit"])
    assert len(fig["data"]) == 2
    assert fig["data"][0]["name"] == "revenue"


def test_build_plotly_viz_single():
    from app.visualization.plotly_integration import build_plotly_viz
    rows = [{"region": "North", "revenue": 100}, {"region": "South", "revenue": 200}]
    result = build_plotly_viz(data=rows, question="revenue by region")
    assert "figure" in result
    assert not result["multi_series"]


def test_build_plotly_viz_multi():
    from app.visualization.plotly_integration import build_plotly_viz
    rows = [{"month": "Jan", "revenue": 100, "cost": 60}]
    result = build_plotly_viz(data=rows, y_cols=["revenue", "cost"])
    assert result["multi_series"]


# ── US-13/14: Conversation Context ───────────────────────────────────────────

def test_context_starts_empty():
    from app.conversation.context_manager import get_conversation_context
    ctx = get_conversation_context("test-session-empty-xyz")
    assert ctx["messages"] == []
    assert ctx["turn_count"] == 0


def test_context_update_and_retrieve():
    from app.conversation.context_manager import update_context_after_turn, get_conversation_context
    chat_id = "test-session-update-123"
    update_context_after_turn(
        chat_id=chat_id,
        user_message="Show me sales by region",
        assistant_answer="Here are the results.",
        sql="SELECT region, SUM(revenue) FROM dbo.sales GROUP BY region",
        result={"columns": ["region", "revenue"], "rows": [{"region": "N", "revenue": 100}]},
        chart_type="bar",
    )
    ctx = get_conversation_context(chat_id)
    assert ctx["last_sql"] is not None
    assert "dbo.sales" in ctx["active_tables"] or "sales" in " ".join(ctx["active_tables"])
    assert ctx["last_chart_type"] == "bar"
    assert ctx["turn_count"] == 1


def test_followup_detection():
    from app.conversation.context_manager import is_followup_question
    assert is_followup_question("Show me those by revenue")
    assert is_followup_question("Can you filter them to last week?")
    assert not is_followup_question("What are total sales by region?")


def test_followup_rewrite_injects_context():
    from app.conversation.context_manager import (
        update_context_after_turn, rewrite_followup_question
    )
    chat_id = "test-followup-rewrite-abc"
    update_context_after_turn(
        chat_id=chat_id,
        user_message="Show sales",
        assistant_answer="Done.",
        sql="SELECT * FROM dbo.orders",
        result={"columns": ["order_id", "amount"], "rows": []},
    )
    rewritten = rewrite_followup_question("Sort those by amount", chat_id)
    assert "amount" in rewritten or "columns" in rewritten.lower()


# ── US-16: Enhanced Cache ─────────────────────────────────────────────────────

def test_cache_miss_then_hit():
    from app.cache.enhanced_query_cache import get_cached_result, set_cached_result, get_cache_stats
    sql = "SELECT TOP 10 * FROM dbo.test_cache_table WHERE id > 999999"
    # Should be a miss first
    result = get_cached_result(sql)
    assert result is None
    # Set and retrieve
    set_cached_result(sql, {"columns": ["id"], "rows": [], "row_count": 0})
    result = get_cached_result(sql)
    assert result is not None
    assert result["from_cache"] is True


def test_cache_stats_structure():
    from app.cache.enhanced_query_cache import get_cache_stats
    stats = get_cache_stats()
    assert "hits" in stats
    assert "misses" in stats
    assert "hit_rate_pct" in stats
    assert "active_keys" in stats


def test_cache_key_deterministic():
    from app.cache.enhanced_query_cache import make_cache_key
    sql = "SELECT   *   FROM   dbo.orders"
    key1 = make_cache_key(sql)
    key2 = make_cache_key("SELECT * FROM dbo.orders")
    assert key1 == key2   # normalisation should produce same key


def test_invalidate_by_table():
    from app.cache.enhanced_query_cache import set_cached_result, invalidate_by_table, get_cached_result
    sql = "SELECT * FROM dbo.sessions WHERE active = 1"
    set_cached_result(sql, {"columns": ["id"], "rows": [], "row_count": 0})
    assert get_cached_result(sql) is not None
    invalidate_by_table("dbo.sessions")
    assert get_cached_result(sql) is None
