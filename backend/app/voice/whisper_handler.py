"""
whisper_handler.py
-------------------
Thin wrapper around Groq's audio transcription API (whisper-large-v3).
Reuses the existing GROQ_API_KEY — no extra credentials needed.

Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.error_handler import structured_error


class WhisperHandler:
    """Transcribes audio files using the Groq Whisper endpoint."""

    MODEL = "whisper-large-v3"
    SUPPORTED_FORMATS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"}

    def transcribe(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        """
        Send *audio_bytes* to Groq's Whisper endpoint and return the transcript.

        Returns:
            {"transcript": str, "model": str, "filename": str}  on success
            structured_error dict                                on failure
        """
        if not settings.GROQ_API_KEY:
            return structured_error(
                tool="whisper",
                message="GROQ_API_KEY is not configured.",
                error_type="ConfigError",
                suggestion="Add GROQ_API_KEY to backend/.env and restart the server.",
            )

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self.SUPPORTED_FORMATS:
            return structured_error(
                tool="whisper",
                message=(
                    f"Unsupported audio format '.{ext}'. "
                    f"Supported: {', '.join(sorted(self.SUPPORTED_FORMATS))}."
                ),
                error_type="UnsupportedFormat",
                suggestion="Re-encode the audio as mp3 or wav before uploading.",
            )

        try:
            # Lazy import so the server starts even when the groq SDK is not installed
            from groq import Groq  # noqa: PLC0415

            client = Groq(api_key=settings.GROQ_API_KEY)
            transcription = client.audio.transcriptions.create(
                model=self.MODEL,
                file=(filename, audio_bytes),
            )
            return {
                "transcript": transcription.text,
                "model": self.MODEL,
                "filename": filename,
            }
        except ImportError:
            return structured_error(
                tool="whisper",
                message="The 'groq' Python package is not installed.",
                error_type="ImportError",
                suggestion="Run: pip install groq",
            )
        except Exception as exc:
            return structured_error(
                tool="whisper",
                message=str(exc),
                error_type="TranscriptionError",
                suggestion=(
                    "Check that the audio file is valid and not corrupted. "
                    "Verify the GROQ_API_KEY has audio transcription access."
                ),
            )


# Module-level singleton
whisper_handler = WhisperHandler()
