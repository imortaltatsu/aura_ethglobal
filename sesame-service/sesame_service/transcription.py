"""STT: OpenAI /v1/audio/transcriptions compatible endpoint using Whisper."""

import os
from typing import Optional

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        model_size = os.environ.get("WHISPER_MODEL", "base")
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _whisper_model


def _get_suffix(filename: Optional[str]) -> str:
    """Infer audio suffix from filename or default to wav."""
    if filename:
        for ext in (".mp3", ".wav", ".webm", ".m4a", ".ogg", ".flac", ".mpeg", ".mpga"):
            if filename.lower().endswith(ext):
                return ext
    return ".wav"


def transcribe_audio(
    audio_bytes: bytes,
    model: str = "whisper-1",
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    response_format: str = "json",
    filename: Optional[str] = None,
) -> dict:
    """Transcribe audio to text using faster-whisper. Returns OpenAI-compatible response."""
    import tempfile

    model_inst = _get_whisper_model()
    suffix = _get_suffix(filename)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        path = f.name

    try:
        segments, info = model_inst.transcribe(path, language=language, initial_prompt=prompt)
        text = " ".join(s.text for s in segments).strip()
    finally:
        os.unlink(path)

    # OpenAI transcription JSON format
    return {
        "text": text,
        "usage": {
            "type": "duration",
            "seconds": 0,  # Could compute from audio if needed
        },
    }
