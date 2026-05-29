"""
tests/test_e2e.py
------------------
End-to-end integration tests covering the full request → response pipeline.
All LLM, DB, and audio-transcription calls are mocked so the suite runs in
the host shell without Docker or external credentials.

Run with:
    cd backend && pytest tests/test_e2e.py -v

Scenarios
---------
1.  Full chat workflow              POST /api/chat
2.  Text2SQL → validate → execute  pipeline smoke test
3.  Spreadsheet upload + query      no LLM required
4.  Voice → chat                   mocked Whisper + run_chat
5.  Cache hit scenario             DB called only once for duplicate SQL
6.  Cache freshness endpoint        GET /api/cache/freshness
7.  Anomaly detection               known outlier flagged correctly
8.  Report generation               POST /api/reports/generate
9.  Tool error recovery             forbidden SQL → structured error, not 500
10. SSE streaming                   chat_id → token → done event sequence
"""
from __future__ import annotations

import io
import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Shared test data ───────────────────────────────────────────────────────────

MOCK_CHAT_RESULT = {
    "chat_id": "test-chat-id-e2e",
    "answer": "Here are the top 10 products by revenue.",
    "tool_calls": [
        {
            "name": "sql_executor",
            "input": {"sql": "SELECT TOP 10 product, revenue FROM dbo.sales"},
            "output": {"rows": [{"product": "Widget", "revenue": 1000}], "row_count": 1},
            "error": None,
        }
    ],
    "chart": None,
    "data": None,
    "from_cache": False,
}

MOCK_DB_RESULT = {
    "columns": ["id", "product", "revenue"],
    "rows": [
        {"id": 1, "product": "Widget", "revenue": 1000},
        {"id": 2, "product": "Gadget", "revenue": 800},
    ],
    "row_count": 2,
}


def _csv_bytes() -> bytes:
    return b"name,region,sales\nAlice,North,120\nBob,South,200\nCarol,North,80\nZara,West,9999\n"


def _wav_bytes() -> bytes:
    """Minimal valid WAV (1 silent sample, mono, 44100 Hz, 16-bit)."""
    return (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        b"\x01\x00\x01\x00\x44\xac\x00\x00\x88X\x01\x00"
        b"\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


# ── App / client fixture ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    from app.main import app
    with TestClient(app) as c:
        yield c


# ── Scenario 1: Full chat workflow ─────────────────────────────────────────────

def test_01_full_chat_workflow(client: TestClient) -> None:
    """POST /api/chat → answer, tool_calls, and chat_id present in response."""
    with patch("app.api.routes_chat.run_chat", return_value=MOCK_CHAT_RESULT):
        response = client.post("/api/chat", json={"message": "Show me the top 10 products"})

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "chat_id" in data
    assert "tool_calls" in data
    assert data["answer"] == MOCK_CHAT_RESULT["answer"]
    assert data["chat_id"] == MOCK_CHAT_RESULT["chat_id"]


# ── Scenario 2: Text2SQL → validate → execute pipeline ────────────────────────

def test_02_text2sql_validate_execute_pipeline(client: TestClient) -> None:
    """NL question → SQL generation → validation → SQL execution pipeline."""
    sql = "SELECT TOP 10 product, SUM(revenue) AS total FROM dbo.sales GROUP BY product"

    # Step 1: generate SQL from natural language
    with patch("app.text2sql.text2sql_pipeline.text2sql_pipeline.generate") as mock_gen:
        mock_gen.return_value = {
            "sql": sql,
            "question": "top products by revenue",
            "validated": True,
            "warnings": [],
        }
        gen_resp = client.post(
            "/api/text2sql/generate",
            json={"question": "top products by revenue"},
        )

    assert gen_resp.status_code == 200
    assert gen_resp.json()["sql"] == sql

    # Step 2: validate the generated SQL
    val_resp = client.post("/api/text2sql/validate", json={"sql": sql})
    assert val_resp.status_code == 200
    assert val_resp.json()["is_valid"] is True

    # Step 3: execute via the sql-executor tool endpoint
    with patch("app.tools.sql_executor.execute_select", return_value=MOCK_DB_RESULT):
        exec_resp = client.post("/api/tools/sql-executor", json={"sql": sql})

    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert "error" not in exec_data
    assert "rows" in exec_data
    assert exec_data["row_count"] == 2


# ── Scenario 3: Spreadsheet upload + direct query ─────────────────────────────

def test_03_spreadsheet_upload_and_query(client: TestClient) -> None:
    """Upload a CSV, verify it appears in the registry, query it, then delete it."""
    csv_bytes = _csv_bytes()
    files = {"file": ("sales_data.csv", io.BytesIO(csv_bytes), "text/csv")}
    upload_resp = client.post("/api/upload/spreadsheet", files=files)
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert "source_id" in upload_data
    source_id = upload_data["source_id"]
    assert upload_data["row_count"] == 4

    # Verify the source appears in the list
    list_resp = client.get("/api/data-sources")
    assert list_resp.status_code == 200
    ids = [s["source_id"] for s in list_resp.json()["sources"]]
    assert source_id in ids

    # Keyword query — "Alice" should match only the Alice row
    query_resp = client.post(
        f"/api/data-sources/{source_id}/query",
        json={"question": "Alice", "limit": 10},
    )
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert "rows" in query_data
    names = [str(r.get("name", "")) for r in query_data["rows"]]
    assert "Alice" in names

    # Cleanup
    del_resp = client.delete(f"/api/data-sources/{source_id}")
    assert del_resp.status_code == 200


# ── Scenario 4: Voice query end-to-end ────────────────────────────────────────

def test_04_voice_query_end_to_end(client: TestClient) -> None:
    """Audio file → Whisper transcript (mocked) → LLM agent (mocked) → answer."""
    with patch("app.voice.whisper_handler.whisper_handler.transcribe") as mock_t, \
         patch("app.agent.graph.run_chat", return_value=MOCK_CHAT_RESULT):
        mock_t.return_value = {
            "transcript": "Show me the top 10 products by revenue",
            "model": "whisper-large-v3",
            "filename": "query.wav",
        }
        files = {"file": ("query.wav", io.BytesIO(_wav_bytes()), "audio/wav")}
        response = client.post("/api/voice/query", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "transcript" in data
    assert "answer" in data
    assert data["source"] == "voice"
    assert "top 10 products" in data["transcript"]


# ── Scenario 5: Cache hit scenario ────────────────────────────────────────────

def test_05_cache_hit_scenario(client: TestClient) -> None:
    """Same SQL posted twice — the DB execute function is called only once."""
    client.post("/api/cache/flush")

    unique_sql = (
        f"SELECT TOP 5 id FROM dbo.orders WHERE region = '{uuid.uuid4().hex}'"
    )

    with patch("app.tools.sql_executor.execute_select", return_value=MOCK_DB_RESULT) as mock_db:
        r1 = client.post("/api/tools/sql-executor", json={"sql": unique_sql})
        r2 = client.post("/api/tools/sql-executor", json={"sql": unique_sql})

    assert r1.status_code == 200
    assert r2.status_code == 200
    # DB must have been queried only once; second response came from cache
    assert mock_db.call_count == 1, (
        f"Expected DB to be called once (cache hit on second request), got {mock_db.call_count}"
    )


# ── Scenario 6: Cache freshness endpoint ──────────────────────────────────────

def test_06_cache_freshness_endpoint(client: TestClient) -> None:
    """GET /api/cache/freshness → 200 with well-formed near-expiry payload."""
    response = client.get("/api/cache/freshness")
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "near_expiry_count" in data
    assert isinstance(data["entries"], list)
    assert data["near_expiry_count"] == len(data["entries"])


# ── Scenario 7: Anomaly detection ─────────────────────────────────────────────

def test_07_anomaly_detection_flags_outlier(client: TestClient) -> None:
    """POST /api/analytics/anomaly with a known outlier → it appears in flagged rows."""
    # 30 normal points (1–30) + one extreme outlier (9999)
    rows = [{"value": float(v)} for v in range(1, 31)] + [{"value": 9999.0}]

    response = client.post(
        "/api/analytics/anomaly",
        json={"rows": rows, "column": "value", "method": "zscore"},
    )
    assert response.status_code == 200
    data = response.json()
    # Response shape: {"outlier_rows": [...], "non_outlier_rows": [...], "outlier_count": N, ...}
    assert "outlier_rows" in data, f"Missing 'outlier_rows' in response: {list(data.keys())}"
    assert data["outlier_count"] >= 1, "Expected at least one outlier"

    flagged = data["outlier_rows"]
    assert len(flagged) >= 1, "Expected at least one outlier row"
    assert any(r["value"] == 9999.0 for r in flagged), (
        f"Outlier value 9999.0 not found in flagged rows: {flagged}"
    )


# ── Scenario 8: Report generation ─────────────────────────────────────────────

def test_08_report_generation(client: TestClient) -> None:
    """POST /api/reports/generate → 200 with report_id and correct download_url."""
    mock_result = {
        "report_id": "rpt-e2e-test",
        "title": "E2E Integration Test Report",
        "path": "/tmp/rpt-e2e-test.pdf",
    }
    with patch("app.api.routes_reports.generate_report", return_value=mock_result):
        response = client.post(
            "/api/reports/generate",
            json={"chat_id": "e2e-chat-session", "title": "E2E Integration Test Report"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] == "rpt-e2e-test"
    assert data["download_url"] == "/api/reports/rpt-e2e-test"
    assert "title" in data


# ── Scenario 9: Tool error recovery ───────────────────────────────────────────

def test_09_tool_error_recovery_forbidden_sql(client: TestClient) -> None:
    """Forbidden DDL and malformed SQL return structured errors — not HTTP 500."""
    # Attempt a forbidden DDL statement
    resp_ddl = client.post("/api/tools/sql-executor", json={"sql": "DROP TABLE dbo.users"})
    assert resp_ddl.status_code == 200, "Expected 200 with structured error payload"
    data_ddl = resp_ddl.json()
    assert "error" in data_ddl, f"Expected 'error' key in response: {data_ddl}"
    assert data_ddl.get("error_type") == "ValidationError"
    assert "suggestion" in data_ddl

    # Other forbidden patterns are also blocked by the validator
    for forbidden_sql in ("INSERT INTO dbo.orders VALUES (1)", "UPDATE dbo.sales SET revenue=0"):
        resp_f = client.post("/api/tools/sql-executor", json={"sql": forbidden_sql})
        assert resp_f.status_code == 200
        assert "error" in resp_f.json(), f"Expected error for: {forbidden_sql}"


# ── Scenario 10: SSE streaming event sequence ──────────────────────────────────

def test_10_sse_streaming_event_sequence(client: TestClient) -> None:
    """POST /api/chat/stream2 → parse SSE frames → chat_id, token, done in order."""
    session_id = f"sse-e2e-{uuid.uuid4().hex[:8]}"

    def _mock_sse(message: str, chat_id: str | None) -> Generator[bytes, None, None]:
        cid = chat_id or session_id
        yield f"event: chat_id\ndata: {cid}\n\n".encode()
        yield b"event: token\ndata: Streaming\n\n"
        yield b"event: token\ndata:  response\n\n"
        yield b"event: done\ndata: [DONE]\n\n"

    with patch("app.api.routes_binit.stream_chat_response", side_effect=_mock_sse):
        response = client.post(
            "/api/chat/stream2",
            json={"message": "test streaming", "chat_id": session_id},
        )

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/event-stream" in content_type

    # Parse SSE frames (blocks separated by double newline)
    raw = response.content.decode()
    events: list[dict[str, str]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        ev: dict[str, str] = {}
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev["type"] = line[len("event:"):].strip()
            elif line.startswith("data:"):
                ev["data"] = line[len("data:"):].strip()
        if "type" in ev:
            events.append(ev)

    types = [e["type"] for e in events]
    assert "chat_id" in types, f"No chat_id event. Got: {types}"
    assert "token" in types,   f"No token event. Got: {types}"
    assert "done" in types,    f"No done event. Got: {types}"

    # chat_id must arrive before done
    assert types.index("chat_id") < types.index("done")
    # Verify the chat_id value echoes back the session ID
    chat_id_events = [e for e in events if e["type"] == "chat_id"]
    assert chat_id_events[0]["data"] == session_id
