"""TTS: OpenAI /v1/audio/speech compatible endpoint using Sesame CSM-1B."""

import io
import os
import tempfile

import numpy as np
import torch

MODEL_ID = "sesame/csm-1b"
SAMPLE_RATE = 24000

_model = None
_processor = None


def _get_model():
    global _model, _processor
    if _model is None:
        from transformers import AutoProcessor, CsmForConditionalGeneration

        # Use single device (cuda:0 or cpu) to avoid "tensors on different devices" errors
        device = os.environ.get("CSM_DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")
        _processor = AutoProcessor.from_pretrained(MODEL_ID)
        _model = CsmForConditionalGeneration.from_pretrained(
            MODEL_ID,
            device_map=device,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        if os.environ.get("NO_TORCH_COMPILE", "0") != "1":
            try:
                _model = torch.compile(_model, mode="reduce-overhead")
            except Exception:
                pass
    return _model, _processor


def text_to_speech(
    text: str,
    voice: str = "alloy",
    response_format: str = "pcm",
    speed: float = 1.0,
) -> bytes:
    """Generate speech from text using Sesame CSM-1B. Returns raw PCM bytes (24kHz mono, 16-bit)."""
    model, processor = _get_model()

    # Sesame uses [0] for speaker id 0. Map OpenAI voice names or use default.
    speaker_id = "0"
    prompt_text = f"[{speaker_id}]{text}"

    conversation = [
        {"role": speaker_id, "content": [{"type": "text", "text": text}]},
    ]
    inputs = processor.apply_chat_template(
        conversation,
        tokenize=True,
        return_dict=True,
    )
    device = next(model.parameters()).device
    inputs = inputs.to(device)

    with torch.no_grad():
        audio = model.generate(**inputs, output_audio=True)

    # Get raw waveform array (model returns tensor, list of tensors, or CsmGenerateOutput.audio)
    if isinstance(audio, (list, tuple)) and len(audio) > 0:
        # Sesame returns list of tensors (one per batch item)
        t = audio[0]
        audio_np = t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)
    elif hasattr(audio, "audio"):
        t = audio.audio[0] if isinstance(audio.audio, (list, tuple)) else audio.audio
        audio_np = t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)
    elif hasattr(audio, "cpu"):
        audio_np = audio.cpu().numpy()
    elif hasattr(audio, "numpy"):
        audio_np = audio.numpy()
    else:
        t = audio
        audio_np = t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)

    if audio_np.ndim > 1:
        audio_np = audio_np.squeeze()

    # Convert float32 [-1,1] to int16 PCM
    audio_int16 = (np.clip(audio_np.astype(np.float32), -1.0, 1.0) * 32767).astype(np.int16)
    pcm_bytes = audio_int16.tobytes()

    if response_format == "pcm":
        return pcm_bytes

    if response_format in ("wav", "mp3"):
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    return pcm_bytes
