# Backend Architecture

This document explains the current backend structure after integrating Himanshu's tool layer with Binit's Text2SQL, validation, visualization, streaming, context, and cache work.

## 1. Entry Point

The backend starts from:

```text
backend/app/main.py
```

`main.py` creates the FastAPI app and mounts the route modules:

```python
app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(binit_router, prefix="/api")
```

Run locally:

```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

## 2. Configuration

Configuration is defined in:

```text
backend/app/core/config.py
```

Secrets are loaded from:

```text
backend/.env
```

Do not hardcode secrets in Python files.

Important `.env` values:

```env
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile

AZURE_SQL_SERVER=streaming-analytic.database.windows.net
AZURE_SQL_DATABASE=real-time-chatbot
AZURE_SQL_USERNAME=capstone-2
AZURE_SQL_PASSWORD=...
AZURE_SQL_DRIVER=ODBC Driver 18 for SQL Server

CACHE_TTL_SECONDS=300
CHAT_TTL_SECONDS=86400
```

## 3. Main Routes

Core routes:

```text
GET  /api/health
POST /api/chat
POST /api/chat/stream
```

Direct tool testing routes:

```text
GET  /api/tools/schema
POST /api/tools/sql-executor
POST /api/tools/rest-api-caller
POST /api/tools/chart-generator
POST /api/tools/data-summarizer
POST /api/tools/export
```

Binit feature routes:

```text
POST /api/text2sql/generate
POST /api/text2sql/refresh-schema
POST /api/text2sql/validate
POST /api/text2sql/advanced
POST /api/viz/chart
GET  /api/conversation/{chat_id}
POST /api/conversation/{chat_id}/reset
POST /api/chat/stream2
GET  /api/cache/stats
POST /api/cache/invalidate
POST /api/cache/flush
```

Note: `/api/chat/stream` and `/api/chat/stream2` now use the same SSE streamer logic. `/api/chat/stream` is the preferred main endpoint.

## 4. LLM And LangGraph

The main LangGraph agent is in:

```text
backend/app/agent/graph.py
```

Groq Llama is connected here:

```python
llm = ChatGroq(
    model=settings.GROQ_MODEL,
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)
```

The agent is created with registered tools:

```python
agent = create_react_agent(llm, REGISTERED_TOOLS)
```

Flow:

```text
FastAPI request
  -> run_chat()
  -> load schema and context
  -> Groq Llama through LangGraph
  -> LLM chooses tools
  -> Python tools execute
  -> tool results return to LLM
  -> final answer returns to FastAPI
```

## 5. Prompt And Schema Injection

The main system prompt is in:

```text
backend/app/agent/prompts.py
```

It tells the model to:

- Use Azure SQL Database T-SQL.
- Generate read-only `SELECT` queries.
- Use `TOP` instead of `LIMIT`.
- Use tools for SQL, charts, summaries, APIs, and exports.
- Use previous context for follow-up questions.

Live schema loading is in:

```text
backend/app/text2sql/schema_registry.py
```

It reads Azure SQL metadata from `INFORMATION_SCHEMA.COLUMNS`, then formats it like:

```text
dbo.orders(order_id int, customer_id int, order_date date, total_amount decimal)
dbo.customers(customer_id int, customer_name varchar, city varchar)
```

That schema text is injected into the LLM prompt.

## 6. Text2SQL

The standalone Text2SQL pipeline is in:

```text
backend/app/text2sql/text2sql_pipeline.py
```

Endpoint:

```text
POST /api/text2sql/generate
```

It:

```text
1. Loads live Azure SQL schema.
2. Sends schema + question to Groq.
3. Extracts SQL from the model output.
4. Validates the SQL.
5. Returns a ready-to-run T-SQL SELECT query.
```

This endpoint generates SQL only. It does not execute the query.

For full natural-language question answering, use:

```text
POST /api/chat
```

## 7. SQL Validation

The stronger shared validator is:

```text
backend/app/text2sql/query_validator.py
```

The older compatibility wrapper is:

```text
backend/app/text2sql/validator.py
```

`validator.py` now delegates to `query_validator.py`, so existing imports still work:

```python
validate_select_query(sql)
```

The validator blocks:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
TRUNCATE
MERGE
EXEC
CREATE
GRANT
REVOKE
xp_cmdshell
openrowset
opendatasource
bulk insert
sp_executesql
```

Allowed query starts:

```text
SELECT
WITH ... SELECT
```

It also adds `TOP 500` to plain `SELECT` queries when no limit exists.

Example:

```sql
select * from support_tickets;
```

becomes:

```sql
SELECT TOP 500 * from support_tickets
```

## 8. SQL Execution

SQL execution is in:

```text
backend/app/db/azure_sql.py
```

The backend connects to Azure SQL using `pyodbc`:

```python
pyodbc.connect(settings.azure_sql_connection_string)
```

The query runs from Python, not from Azure Query Editor.

Runtime flow:

```text
FastAPI backend on local machine or container
  -> pyodbc ODBC Driver 18
  -> Azure SQL Database
  -> Azure SQL executes query
  -> rows return to Python
  -> FastAPI returns JSON or sends data back to the LLM
```

Azure Query Editor is only for manual SQL testing in the Azure Portal.

## 9. Registered Tools

Tools are registered in:

```text
backend/app/tools/__init__.py
```

Current registered tools:

```text
sql_executor
rest_api_caller
data_summarizer
export_tool
chart_generator
dynamic_chart
plotly_viz
advanced_sql
cache_management
```

The LLM does not directly execute Python. LangGraph receives the model's tool call and runs the matching Python function.

## 10. Tool Details

### SQL Executor

File:

```text
backend/app/tools/sql_executor.py
```

It:

```text
1. Validates SQL through validate_select_query().
2. Checks enhanced query cache.
3. Executes SQL against Azure SQL if cache misses.
4. Stores result in enhanced cache.
5. Returns columns, rows, row_count, truncated, and from_cache.
```

### REST API Caller

File:

```text
backend/app/tools/rest_api_caller.py
```

It calls external APIs using safe `GET` requests through `httpx`.

### Data Summarizer

File:

```text
backend/app/tools/data_summarizer.py
```

It summarizes rows with:

```text
row count
columns
example rows
numeric min/max/avg/total
```

### Export Tool

File:

```text
backend/app/tools/export_tool.py
```

It exports rows to CSV or JSON under:

```text
backend/exports/
```

### Chart Generator

File:

```text
backend/app/tools/chart_generator.py
```

This is the original Plotly figure generator. It is still registered for backwards compatibility and direct endpoint testing.

### Dynamic Chart

File:

```text
backend/app/visualization/dynamic_chart.py
```

It selects chart types based on data shape and question text.

Examples:

```text
date/time x-axis -> line
few categories -> pie
distribution question -> histogram
otherwise -> bar
```

### Plotly Visualization

File:

```text
backend/app/visualization/plotly_integration.py
```

It builds themed Plotly figures and supports single-series or multi-series charts.

### Advanced SQL

File:

```text
backend/app/text2sql/advanced_sql.py
```

It can build:

```text
aggregation queries
window function queries
date filter queries
join queries
CTE queries
```

Endpoint:

```text
POST /api/text2sql/advanced
```

### Cache Management

File:

```text
backend/app/cache/enhanced_query_cache.py
```

It exposes cache stats, table invalidation, full flush, and a `cache_management` tool for the agent.

## 11. Cache Flow

The active query cache is:

```text
backend/app/cache/enhanced_query_cache.py
```

It uses the process memory store:

```text
backend/app/cache/memory_cache.py
```

Flow:

```text
Validated SQL
  -> hash SQL into cache key
  -> check memory cache
  -> if hit, return cached result
  -> if miss, execute Azure SQL
  -> store result with TTL
```

Cache endpoints:

```text
GET  /api/cache/stats
POST /api/cache/invalidate
POST /api/cache/flush
```

The old file `backend/app/cache/query_cache.py` is no longer the active query cache. It can be removed later after compatibility cleanup.

## 12. Conversation Context

Basic message memory is in:

```text
backend/app/agent/memory.py
```

Richer analytical context is in:

```text
backend/app/conversation/context_manager.py
```

It tracks:

```text
messages
last_sql
last_columns
last_rows
last_chart_type
active_tables
turn_count
```

The normal `/api/chat` path now uses this richer context through:

```python
prepare_question()
update_context_after_turn()
```

This supports follow-up questions like:

```text
Now filter those to only high priority tickets
```

The same `chat_id` should be reused across turns.

## 13. Streaming

Streaming code is in:

```text
backend/app/streaming/sse_streamer.py
```

Preferred streaming endpoint:

```text
POST /api/chat/stream
```

Compatibility endpoint:

```text
POST /api/chat/stream2
```

SSE events:

```text
chat_id
meta
tool_start
tool_end
token
done
error
```

Important note: the current streamer invokes the LangGraph agent first, then streams the final answer in chunks while also emitting tool lifecycle events. It is SSE-compatible and frontend-friendly, but it is not pure Groq token streaming through the whole tool loop yet.

## 14. Direct Tool Testing

Use Swagger:

```text
http://localhost:8000/docs
```

Test SQL executor:

```text
POST /api/tools/sql-executor
```

Request:

```json
{
  "sql": "select * from support_tickets;"
}
```

This tests:

```text
FastAPI -> SQL Executor -> Azure SQL -> JSON response
```

It does not use Groq.

## 15. Chat Testing

Use:

```text
POST /api/chat
```

Request:

```json
{
  "message": "How many support tickets are open by priority?"
}
```

This tests:

```text
FastAPI -> LangGraph -> Groq Llama -> tools -> Azure SQL -> final answer
```

Follow-up example:

```json
{
  "chat_id": "reuse-the-chat-id-from-previous-response",
  "message": "Now show only high priority tickets"
}
```

## 16. Important Files

```text
backend/app/main.py                         FastAPI entry point
backend/app/core/config.py                  Settings and environment loading
backend/app/api/routes_chat.py              Main chat and streaming routes
backend/app/api/routes_tools.py             Direct tool test routes
backend/app/api/routes_binit.py             Text2SQL, viz, context, cache routes
backend/app/agent/graph.py                  Groq + LangGraph chat agent
backend/app/agent/prompts.py                System prompt
backend/app/agent/memory.py                 Basic chat memory
backend/app/conversation/context_manager.py Rich follow-up context
backend/app/tools/__init__.py               Registered LangGraph tools
backend/app/tools/sql_executor.py           SQL execution tool
backend/app/tools/rest_api_caller.py        REST API tool
backend/app/tools/data_summarizer.py        Summary tool
backend/app/tools/export_tool.py            Export tool
backend/app/tools/chart_generator.py        Original chart tool
backend/app/visualization/dynamic_chart.py  Dynamic chart selection
backend/app/visualization/plotly_integration.py Plotly figure integration
backend/app/text2sql/schema_registry.py     Live Azure SQL schema loader
backend/app/text2sql/text2sql_pipeline.py   Standalone Text2SQL pipeline
backend/app/text2sql/query_validator.py     Main SQL validator
backend/app/text2sql/validator.py           Compatibility validator wrapper
backend/app/text2sql/advanced_sql.py        Advanced SQL builder
backend/app/db/azure_sql.py                 Azure SQL connection and execution
backend/app/cache/memory_cache.py           In-memory TTL cache
backend/app/cache/enhanced_query_cache.py   Active query cache with stats/invalidation
backend/app/streaming/sse_streamer.py       SSE chat streaming
backend/tests/                              Unit tests
```

## 17. Optional / Demo Files

These are not required at runtime if your Azure SQL database already has tables and data:

```text
backend/app/db/sample_schema.sql
backend/app/db/seed_data.sql
```

They can be kept as demo/reference files.

