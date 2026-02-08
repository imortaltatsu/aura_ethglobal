"""FastAPI app exposing OpenAI-compatible /v1/audio/speech and /v1/audio/transcriptions."""

import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .speech import text_to_speech
from .transcription import transcribe_audio

# Avoid torch compile on first import for faster startup
os.environ.setdefault("NO_TORCH_COMPILE", "1")


@asynccontextmanager
async def lifespan(app):
    """Lifespan handler - load models on startup."""
    yield
    # Shutdown cleanup if needed


try:
    from fastapi import FastAPI
except ImportError:
    from fastapi import FastAPI

app = FastAPI(title="Sesame OpenAI-compatible API", lifespan=lifespan)

v1_router = APIRouter(prefix="/v1", tags=["v1"])


class SpeechRequest(BaseModel):
    model: str = "sesame-csm-1b"
    voice: str = "alloy"
    input: str  # noqa: A003
    response_format: str = "pcm"
    speed: float = 1.0


@v1_router.post("/audio/speech")
async def create_speech(req: SpeechRequest):
    """OpenAI-compatible TTS: text -> audio. Uses Sesame CSM-1B."""
    if not req.input or len(req.input.strip()) == 0:
        raise HTTPException(status_code=400, detail="input is required")
    try:
        audio_bytes = text_to_speech(
            text=req.input,
            voice=req.voice,
            response_format=req.response_format,
            speed=req.speed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    media_type = "audio/pcm" if req.response_format == "pcm" else "audio/wav"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type=media_type,
    )


@v1_router.post("/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str = Form(None),
    prompt: str = Form(None),
    response_format: str = Form("json"),
):
    """OpenAI-compatible STT: audio -> text. Uses Whisper (Sesame CSM does not support ASR)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="file is required")
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="file is empty")
    try:
        result = transcribe_audio(
            audio_bytes=audio_bytes,
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format,
            filename=file.filename,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if response_format == "text":
        return result["text"]
    return result


app.include_router(v1_router)