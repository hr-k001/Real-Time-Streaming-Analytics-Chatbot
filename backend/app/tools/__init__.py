"""
app/tools/__init__.py
----------------------
Registers ALL LangGraph tools — Himanshu's original set, Binit's additions,
and the new Feature 3 anomaly detection tool.
Import REGISTERED_TOOLS anywhere to get the full tool list for the agent.
"""
# ── Himanshu's tools (US-03 to US-07) ────────────────────────────────────────
from app.tools.chart_generator import chart_generator_tool
from app.tools.data_summarizer import data_summarizer_tool
from app.tools.export_tool import export_tool
from app.tools.rest_api_caller import rest_api_caller_tool
from app.tools.sql_executor import sql_executor_tool

# ── Binit's tools (US-10 to US-12, US-16) ────────────────────────────────────
from app.text2sql.advanced_sql import advanced_sql_tool
from app.visualization.dynamic_chart import dynamic_chart_tool
from app.visualization.plotly_integration import plotly_viz_tool
from app.cache.enhanced_query_cache import cache_management_tool

# ── Feature 2: Spreadsheet Integration ───────────────────────────────────────
from app.data_sources.spreadsheet_handler import spreadsheet_query_tool

# ── Feature 3: Anomaly Detection ──────────────────────────────────────────────
from app.analytics.anomaly_detector import anomaly_detection_tool

REGISTERED_TOOLS = [
    # Core data tools
    sql_executor_tool,
    rest_api_caller_tool,
    data_summarizer_tool,
    export_tool,

    # Visualization (Binit US-11/12 replaces/augments Himanshu's chart_generator)
    chart_generator_tool,      # keep for backwards compat
    dynamic_chart_tool,        # US-11: smart type selection
    plotly_viz_tool,           # US-12: themed multi-series

    # Cache management (Binit US-16)
    cache_management_tool,

    # Anomaly detection (Feature 3)
    anomaly_detection_tool,

    # Spreadsheet integration (Feature 2)
    spreadsheet_query_tool,
]

# Normal chat agent tools. Keep feature tools available, but use one chart tool
# to avoid repeated visualization-tool loops.
CHAT_AGENT_TOOLS = [
    sql_executor_tool,
    rest_api_caller_tool,
    export_tool,
    chart_generator_tool,
    advanced_sql_tool,
    cache_management_tool,
    anomaly_detection_tool,
    spreadsheet_query_tool,
]
