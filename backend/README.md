# Real-Time Streaming Analytics Chatbot Backend

Backend implementation for my(himanshu) user stories:

- US-01 Project Setup
- US-02 BI Chatbot Architecture
- US-03 SQL Executor Tool
- US-04 REST API Caller Tool
- US-05 Chart Generator Tool
- US-06 Data Summarizer Tool
- US-07 Export Tool

## Local Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Fill these values in `.env`: (i have already shared everything in the teams chat just create your own groq api)

```env
GROQ_API_KEY=...
AZURE_SQL_PASSWORD=...
```

Install Microsoft ODBC Driver 18 for SQL Server on your machine if `pyodbc` cannot connect.

## Run

```powershell
uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://localhost:8000/docs
```

## Azure SQL

Configured defaults:

```text
Server: streaming-analytic.database.windows.net
Database: real-time-chatbot
Username: capstone-2
```

Run `app/db/sample_schema.sql` and then `app/db/seed_data.sql` inside Azure SQL Query Editor or Azure Data Studio to create sample BI tables.

## Main Endpoints

```text
GET  /api/health
POST /api/chat
POST /api/chat/stream
GET  /api/tools/schema
POST /api/tools/sql-executor
POST /api/tools/rest-api-caller
POST /api/tools/chart-generator
POST /api/tools/data-summarizer
POST /api/tools/export
```

## Example Chat Request

```json
{
  "message": "Show total sales by region and create a chart"
}
```
