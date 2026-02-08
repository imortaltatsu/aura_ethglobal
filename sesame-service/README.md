# Sesame Service

OpenAI-compatible REST API for TTS (Sesame CSM-1B) and STT (Whisper).

## Endpoints

- `POST /v1/audio/speech` - Text-to-speech (Sesame CSM-1B)
- `POST /v1/audio/transcriptions` - Speech-to-text (faster-whisper)

## Run

```bash
uv sync
cp .env.example .env
# Set HF_TOKEN if needed for gated models
uv run uvicorn sesame_service.main:app --host 0.0.0.0 --port 8000
```

## Environment

- `HF_TOKEN` - HuggingFace token for sesame/csm-1b
- `CSM_DEVICE_MAP` - auto, balanced, or cuda:0
- `NO_TORCH_COMPILE` - 1 to disable torch.compile
- `WHISPER_MODEL` - tiny, base, small, medium, large-v3
