"""
routes_voice.py
----------------
Feature 5: Voice query endpoints using Groq Whisper (whisper-large-v3).

  POST /api/voice/transcribe — Upload audio, receive transcript
  POST /api/voice/query      — Upload audio, transcribe, run through LLM agent
"""
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.voice.whisper_handler import whisper_handler

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Transcribe an uploaded audio file using Groq Whisper.
    Returns {"transcript": str, "model": str, "filename": str}.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    result = whisper_handler.transcribe(content, file.filename or "audio.wav")
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.post("/query")
async def voice_query(
    file: UploadFile = File(...),
    chat_id: str | None = Form(None),
) -> dict[str, Any]:
    """
    Transcribe audio then run the transcript through the LLM agent.
    Returns the same shape as POST /api/chat plus a 'transcript' field.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    transcription = whisper_handler.transcribe(content, file.filename or "audio.wav")
    if "error" in transcription:
        raise HTTPException(status_code=422, detail=transcription["error"])

    from app.agent.graph import run_chat  # deferred: langgraph only available in Docker

    transcript = transcription["transcript"]
    chat_result = run_chat(transcript, chat_id)
    return {
        **chat_result,
        "transcript": transcript,
        "source": "voice",
    }
