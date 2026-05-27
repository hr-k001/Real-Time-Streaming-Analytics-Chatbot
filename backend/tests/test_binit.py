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


# ── Feature 7: Tool Error Handling ───────────────────────────────────────────

def test_with_retry_succeeds_after_transient_failure():
    """with_retry should retry on matching exceptions and return on success."""
    from app.core.error_handler import with_retry

    attempts = {"n": 0}

    @with_retry(max_attempts=3, delay_seconds=0, retryable_exceptions=(ValueError,))
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("transient")
        return "ok"

    result = flaky()
    assert result == "ok"
    assert attempts["n"] == 3


def test_with_retry_raises_after_max_attempts():
    """with_retry should re-raise the last exception after exhausting attempts."""
    from app.core.error_handler import with_retry

    @with_retry(max_attempts=2, delay_seconds=0, retryable_exceptions=(RuntimeError,))
    def always_fails():
        raise RuntimeError("permanent failure")

    with pytest.raises(RuntimeError, match="permanent failure"):
        always_fails()


def test_with_retry_does_not_retry_non_matching_exception():
    """with_retry should not catch exceptions not in retryable_exceptions."""
    from app.core.error_handler import with_retry

    calls = {"n": 0}

    @with_retry(max_attempts=3, delay_seconds=0, retryable_exceptions=(ValueError,))
    def raises_type_error():
        calls["n"] += 1
        raise TypeError("not retryable")

    with pytest.raises(TypeError):
        raises_type_error()
    assert calls["n"] == 1  # only 1 attempt, not 3


def test_structured_error_shape():
    """structured_error should produce the expected dict shape."""
    from app.core.error_handler import structured_error

    err = structured_error(
        tool="my_tool",
        message="something went wrong",
        error_type="DBError",
        retries_attempted=3,
        suggestion="check your SQL",
    )
    assert err["tool"] == "my_tool"
    assert err["error"] == "something went wrong"
    assert err["error_type"] == "DBError"
    assert err["retries_attempted"] == 3
    assert err["suggestion"] == "check your SQL"


def test_chart_generator_returns_structured_error_on_empty():
    """chart_generator should return a structured_error dict for empty input."""
    from app.tools.chart_generator import generate_chart

    result = generate_chart(data=[], x=None, y=None)
    assert "error" in result
    assert result.get("tool") == "chart_generator"


def test_data_summarizer_handles_null_values():
    """data_summarizer should not crash and should report null_counts."""
    from app.tools.data_summarizer import summarize_data

    rows = [
        {"sales": 100, "region": "North"},
        {"sales": None, "region": "South"},
        {"sales": 200, "region": None},
    ]
    result = summarize_data(rows)
    assert result["row_count"] == 3
    assert "numeric_stats" in result
    assert result["numeric_stats"]["sales"]["non_null_count"] == 2
    assert result["null_counts"].get("sales") == 1


# ── Feature 1: Cache TTL Refresh ─────────────────────────────────────────────

def test_memory_cache_get_expiry_info():
    """get_expiry_info should return remaining TTL for a live key."""
    from app.cache.memory_cache import MemoryCache

    c = MemoryCache()
    c.set("mykey", {"v": 1}, ttl_seconds=300)
    info = c.get_expiry_info("mykey")
    assert info is not None
    assert "remaining_seconds" in info
    assert info["remaining_seconds"] > 299


def test_memory_cache_get_expiry_info_missing_key():
    """get_expiry_info should return None for absent keys."""
    from app.cache.memory_cache import MemoryCache

    c = MemoryCache()
    assert c.get_expiry_info("nonexistent") is None


def test_memory_cache_all_keys():
    """all_keys should list all non-expired cache keys."""
    from app.cache.memory_cache import MemoryCache

    c = MemoryCache()
    c.set("a", 1, 300)
    c.set("b", 2, 300)
    keys = c.all_keys()
    assert "a" in keys
    assert "b" in keys


def test_set_cached_result_stores_sql_in_index():
    """set_cached_result should index original SQL for refresher lookup."""
    from app.cache.enhanced_query_cache import (
        set_cached_result, _key_sql_index, make_cache_key
    )

    sql = "SELECT TOP 5 * FROM dbo.refresh_test_xyz WHERE id > 0"
    set_cached_result(sql, {"columns": ["id"], "rows": [], "row_count": 0})
    key = make_cache_key(sql)
    assert key in _key_sql_index
    assert _key_sql_index[key] == sql


def test_get_near_expiry_keys_empty_on_fresh_cache():
    """A freshly-set key should not appear as near-expiry (0% elapsed)."""
    from app.cache.enhanced_query_cache import set_cached_result, get_near_expiry_keys

    sql = "SELECT TOP 1 * FROM dbo.near_expiry_test WHERE id = 99999"
    set_cached_result(sql, {"columns": ["id"], "rows": [], "row_count": 0}, ttl=300)
    # With threshold_pct=0.8 and only milliseconds elapsed, should not be near-expiry
    near = get_near_expiry_keys(threshold_pct=0.8)
    fresh_keys = [e["sql"] for e in near]
    assert sql not in fresh_keys


def test_get_freshness_report_is_list():
    """get_freshness_report should return a list (may be empty)."""
    from app.cache.cache_refresher import get_freshness_report

    report = get_freshness_report()
    assert isinstance(report, list)


# ── Feature 3: Anomaly Detection ─────────────────────────────────────────────

def test_anomaly_detect_zscore_flags_outlier():
    """Z-score method should flag a clear statistical outlier."""
    from app.analytics.anomaly_detector import detect_anomalies

    normals = [45, 52, 48, 61, 39, 55, 50, 47, 53, 44, 58, 42, 51, 49, 56]
    rows = [{"sales": float(v), "region": "A"} for v in normals] + [{"sales": 500.0, "region": "A"}]
    result = detect_anomalies(rows, columns=["sales", "region"], column="sales", method="zscore")
    assert result["outlier_count"] == 1
    assert result["outlier_rows"][0]["sales"] == 500.0
    assert result["outlier_rows"][0]["_is_outlier"] is True
    assert "_z_score" in result["outlier_rows"][0]


def test_anomaly_detect_iqr_flags_outlier():
    """IQR method should flag an extreme outlier."""
    from app.analytics.anomaly_detector import detect_anomalies

    rows = [{"val": float(v)} for v in [10, 11, 10, 12, 9, 11, 10]] + [{"val": 999.0}]
    result = detect_anomalies(rows, columns=["val"], method="iqr")
    assert result["outlier_count"] >= 1
    outlier_vals = [r["val"] for r in result["outlier_rows"]]
    assert 999.0 in outlier_vals


def test_anomaly_auto_selects_iqr_small_dataset():
    """auto method should choose IQR when n < 30."""
    from app.analytics.anomaly_detector import detect_anomalies

    rows = [{"v": float(i)} for i in range(10)] + [{"v": 999.0}]
    result = detect_anomalies(rows, columns=["v"], method="auto")
    assert result["method_used"] == "iqr"


def test_anomaly_auto_selects_zscore_large_dataset():
    """auto method should choose z-score when n >= 30."""
    from app.analytics.anomaly_detector import detect_anomalies

    rows = [{"v": float(i)} for i in range(30)] + [{"v": 9999.0}]
    result = detect_anomalies(rows, columns=["v"], method="auto")
    assert result["method_used"] == "zscore"


def test_anomaly_empty_rows_returns_error():
    from app.analytics.anomaly_detector import detect_anomalies

    result = detect_anomalies([], [])
    assert "error" in result
    assert result.get("error_type") == "EmptyDataError"


def test_anomaly_no_numeric_column_returns_error():
    from app.analytics.anomaly_detector import detect_anomalies

    rows = [{"name": "Alice"}, {"name": "Bob"}]
    result = detect_anomalies(rows, ["name"])
    assert "error" in result
    assert result.get("error_type") == "NoNumericColumn"


def test_anomaly_stats_included():
    """Result should include descriptive statistics for the analysed column."""
    from app.analytics.anomaly_detector import detect_anomalies

    rows = [{"sales": float(v)} for v in [10, 20, 30, 40, 50]]
    result = detect_anomalies(rows, columns=["sales"], method="iqr")
    stats = result["stats"]
    assert "mean" in stats
    assert "min" in stats
    assert "max" in stats
    assert "median" in stats


def test_anomaly_default_column_is_first_numeric():
    """When column is not specified, the first numeric column should be used."""
    from app.analytics.anomaly_detector import detect_anomalies

    rows = [{"name": "A", "score": float(v)} for v in [10, 20, 30, 500]]
    result = detect_anomalies(rows, columns=["name", "score"], method="iqr")
    assert result["column"] == "score"


# ── Feature 2: Spreadsheet Integration ───────────────────────────────────────

def test_spreadsheet_load_csv_returns_source_id():
    """Loading a CSV should return a non-empty string source_id."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid = reg.load(b"name,sales\nAlice,100\nBob,200\n", "test.csv")
    assert isinstance(sid, str)
    assert len(sid) > 0


def test_spreadsheet_schema_has_correct_columns():
    """Schema should report correct column names and row count."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid = reg.load(b"name,sales,region\nAlice,100,North\nBob,200,South\n", "test.csv")
    schema = reg.get_schema(sid)
    col_names = [c["name"] for c in schema["columns"]]
    assert "name" in col_names
    assert "sales" in col_names
    assert "region" in col_names
    assert schema["row_count"] == 2


def test_spreadsheet_query_returns_all_rows():
    """Querying with no filter should return all rows."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid = reg.load(b"name,sales\nAlice,100\nBob,200\nCarol,300\n", "data.csv")
    result = reg.query(sid)
    assert result["row_count"] == 3
    names = [r["name"] for r in result["rows"]]
    assert "Alice" in names and "Carol" in names


def test_spreadsheet_keyword_filter_narrows_rows():
    """Keyword search should return only rows containing the keyword in a string column."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid = reg.load(b"name,region\nAlice,North\nBob,South\nCarol,North\n", "r.csv")
    result = reg.query(sid, question="North")
    assert result["row_count"] == 2
    assert all(r["region"] == "North" for r in result["rows"])


def test_spreadsheet_column_filter_exact_match():
    """Column=value filter should return only exactly matching rows."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid = reg.load(b"name,region\nAlice,North\nBob,South\nCarol,North\n", "r.csv")
    result = reg.query(sid, filters={"region": "South"})
    assert result["row_count"] == 1
    assert result["rows"][0]["name"] == "Bob"


def test_spreadsheet_unknown_source_returns_error():
    """Querying a non-existent source_id should return a structured NotFoundError."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    result = reg.query("does-not-exist-xyz")
    assert "error" in result
    assert result["error_type"] == "NotFoundError"


def test_spreadsheet_remove_source():
    """After removing a source, get_schema should return None."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid = reg.load(b"a,b\n1,2\n", "small.csv")
    assert reg.get_schema(sid) is not None
    assert reg.remove(sid) is True
    assert reg.get_schema(sid) is None


def test_spreadsheet_list_sources_includes_all_loaded():
    """list_sources should include every loaded source_id."""
    from app.data_sources.spreadsheet_handler import SpreadsheetRegistry

    reg = SpreadsheetRegistry()
    sid1 = reg.load(b"x,y\n1,2\n", "a.csv")
    sid2 = reg.load(b"x,y\n3,4\n", "b.csv")
    source_ids = [s["source_id"] for s in reg.list_sources()]
    assert sid1 in source_ids
    assert sid2 in source_ids


# ── Feature 5: Voice / Whisper ─────────────────────────────────────────────────

def test_whisper_missing_api_key_returns_config_error():
    """With no GROQ_API_KEY configured, transcribe should return a ConfigError."""
    from app.voice.whisper_handler import WhisperHandler
    from app.core.config import settings

    handler = WhisperHandler()
    orig = settings.GROQ_API_KEY
    settings.GROQ_API_KEY = ""
    result = handler.transcribe(b"audio", "test.wav")
    settings.GROQ_API_KEY = orig
    assert "error" in result
    assert result["error_type"] == "ConfigError"


def test_whisper_unsupported_format_returns_error():
    """An unsupported file extension should return a UnsupportedFormat error."""
    from app.voice.whisper_handler import WhisperHandler
    from app.core.config import settings

    handler = WhisperHandler()
    orig = settings.GROQ_API_KEY
    settings.GROQ_API_KEY = "fake-key-for-test"
    result = handler.transcribe(b"data", "audio.pdf")
    settings.GROQ_API_KEY = orig
    assert "error" in result
    assert result["error_type"] == "UnsupportedFormat"


def test_whisper_groq_not_installed_returns_import_error():
    """When the groq SDK is absent, transcribe should return an ImportError dict."""
    from app.voice.whisper_handler import WhisperHandler
    from app.core.config import settings

    handler = WhisperHandler()
    orig = settings.GROQ_API_KEY
    settings.GROQ_API_KEY = "fake-key-for-test"
    # In the host shell environment groq is not installed, so ImportError is raised
    result = handler.transcribe(b"data", "audio.wav")
    settings.GROQ_API_KEY = orig
    assert "error" in result
    assert result["error_type"] == "ImportError"


# ── Feature 4: PDF Report Generation ─────────────────────────────────────────

def test_report_escape_sanitizes_xml_chars():
    """_escape should convert XML-special characters to safe entities."""
    from app.reports.report_generator import _escape

    assert _escape("a & b") == "a &amp; b"
    assert _escape("<tag>") == "&lt;tag&gt;"
    assert _escape('"quoted"') == "&quot;quoted&quot;"


def test_report_generator_creates_pdf():
    """generate_report should create a PDF and return a report_id and path."""
    import tempfile
    from app.reports.report_generator import generate_report
    from app.core.config import settings

    orig = settings.REPORTS_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        settings.REPORTS_DIR = tmpdir
        result = generate_report("test-chat-pdf-001", "Unit Test Report")
        settings.REPORTS_DIR = orig

    assert "report_id" in result
    assert "path" in result
    assert result["title"] == "Unit Test Report"
    assert "error" not in result


def test_report_generator_pdf_file_exists_on_disk():
    """The generated PDF path should exist as a real file."""
    import os, tempfile
    from app.reports.report_generator import generate_report
    from app.core.config import settings

    orig = settings.REPORTS_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        settings.REPORTS_DIR = tmpdir
        result = generate_report("test-chat-pdf-002")
        exists = os.path.isfile(result["path"])
        settings.REPORTS_DIR = orig

    assert exists


def test_report_generator_returns_error_when_reportlab_unavailable():
    """If reportlab cannot be imported, generate_report should return a structured error."""
    from unittest.mock import patch
    from app.reports.report_generator import generate_report
    import app.reports.report_generator as rg

    with patch.object(rg, "_get_reportlab", side_effect=ImportError("not installed")):
        result = generate_report("test-chat-missing-rl-003")

    assert "error" in result
    assert result["error_type"] == "ImportError"
