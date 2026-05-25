from app.tools.chart_generator import chart_generator_tool
from app.tools.data_summarizer import data_summarizer_tool
from app.tools.export_tool import export_tool
from app.tools.rest_api_caller import rest_api_caller_tool
from app.tools.sql_executor import sql_executor_tool

REGISTERED_TOOLS = [
    sql_executor_tool,
    rest_api_caller_tool,
    chart_generator_tool,
    data_summarizer_tool,
    export_tool,
]
