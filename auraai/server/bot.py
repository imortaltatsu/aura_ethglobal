#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""auraai - Pipecat Voice Agent

Cascade pipeline: STT (Whisper) → LLM (gpt-oss:20b/Ollama) → TTS (Sesame CSM)

- STT: Local Whisper
- TTS: XTTS (Coqui, natural-sounding, requires Docker server)
- LLM: Ollama at OLLAMA_HOST (default https://gpt.adityaberry.me)
- Memory: disabled

Run: uv run bot.py
"""


from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import TurnAnalyzerUserTurnStopStrategy
import aiofiles
from pipecat.runner.types import SmallWebRTCRunnerArguments
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import LLMRunFrame
from pipecat.processors.aggregators.llm_response_universal import AssistantTurnStoppedMessage, UserTurnStoppedMessage
import io
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat_whisker import WhiskerObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from loguru import logger
from pipecat.transports.base_transport import BaseTransport
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
import wave
try:
    from pipecat_tail.observer import TailObserver
    _TAIL_AVAILABLE = True
except ImportError:
    TailObserver = None  # type: ignore[misc, assignment]
    _TAIL_AVAILABLE = False
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
import aiohttp
from pipecat.services.xtts.tts import XTTSService
from pipecat.transcriptions.language import Language
import datetime
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.services.ollama.llm import OLLamaLLMService
from dotenv import load_dotenv
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
import os
from pipecat.runner.types import RunnerArguments
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.base_transport import TransportParams

from prompts import SYSTEM_PROMPT
from sui_context import fetch_sui_top_tokens
from tools import (
    get_tools_schema,
    get_current_time,
    get_current_date,
    get_sui_token_prices,
    analyze_portfolio,
    spawn_wallet,
    get_fund_wallet_info,
    get_wallet_balance,
    dipcoin_swap,
)

load_dotenv(override=True)


def _get_mcp_server_params():
    """Build MCP server params from env. Returns None if MCP not configured."""
    import json

    url = os.getenv("MCP_SERVER_URL", "").strip()
    if url:
        try:
            from mcp.client.session_group import SseServerParameters

            return SseServerParameters(url=url)
        except ImportError:
            logger.warning("MCP not installed; set pipecat-ai[mcp]. Ignoring MCP_SERVER_URL.")
            return None

    cmd = os.getenv("MCP_STDIO_COMMAND", "").strip()
    if cmd:
        try:
            from mcp import StdioServerParameters

            raw = os.getenv("MCP_STDIO_ARGS", "[]").strip()
            try:
                args = json.loads(raw) if raw.startswith("[") else [a.strip() for a in raw.split(",") if a.strip()]
            except json.JSONDecodeError:
                args = [a.strip() for a in raw.split(",") if a.strip()]
            return StdioServerParameters(command=cmd, args=args)
        except ImportError:
            logger.warning("MCP not installed; set pipecat-ai[mcp]. Ignoring MCP_STDIO_COMMAND.")
            return None

    return None

# Increase audio input timeout (default 1.0s) to reduce "audio not received" warnings during natural pauses
import pipecat.transports.base_input as _base_input
_base_input.AUDIO_INPUT_TIMEOUT_SECS = float(os.getenv("AUDIO_INPUT_TIMEOUT_SECS", "3.0"))


async def save_audio_file(audio: bytes, filename: str, sample_rate: int, num_channels: int):
    """Save audio data to a WAV file."""
    if len(audio) > 0:
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            async with aiofiles.open(filename, "wb") as file:
                await file.write(buffer.getvalue())
        logger.info(f"Audio saved to {filename}")




async def run_bot(transport: BaseTransport):
    """Main bot logic."""
    logger.info("Starting bot")

    # Speech-to-Text: Local Whisper (GPU for lower latency)
    stt = WhisperSTTService(
        model=os.getenv("WHISPER_MODEL", "base"),
        device=os.getenv("WHISPER_DEVICE", "cuda"),
    )

    # Text-to-Speech: XTTS (Coqui, natural-sounding)
    # Requires: docker run --gpus=all -e COQUI_TOS_AGREED=1 -p 8020:80 ghcr.io/coqui-ai/xtts-streaming-server:latest-cuda121
    xtts_base_url = os.getenv("XTTS_BASE_URL", "http://127.0.0.1:8020").rstrip("/")
    xtts_voice = os.getenv("XTTS_VOICE_ID", "Claribel Dervla")
    lang = getattr(Language, os.getenv("XTTS_LANGUAGE", "EN"), Language.EN)

    async with aiohttp.ClientSession() as session:
        tts = XTTSService(
            voice_id=xtts_voice,
            base_url=xtts_base_url,
            aiohttp_session=session,
            language=lang,
        )

        # LLM: gpt-oss:20b via Ollama (OLLAMA_HOST or OLLAMA_BASE_URL)
        ollama_host = os.getenv("OLLAMA_HOST", "https://gpt.adityaberry.me")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL") or (
            ollama_host.rstrip("/") + "/v1" if not ollama_host.endswith("/v1") else ollama_host.rstrip("/")
        )
        llm = OLLamaLLMService(
            model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
            base_url=ollama_base_url,
        )

        # Register built-in tool handlers
        for handler in (
            get_current_time,
            get_current_date,
            get_sui_token_prices,
            analyze_portfolio,
            spawn_wallet,
            get_fund_wallet_info,
            get_wallet_balance,
            dipcoin_swap,
        ):
            llm.register_direct_function(handler, cancel_on_interruption=True)

        # Merge built-in tools with MCP tools (if configured)
        tools = get_tools_schema()
        all_tools = list(tools.standard_tools)

        mcp_params = _get_mcp_server_params()
        if mcp_params:
            try:
                from pipecat.services.mcp_service import MCPClient
                from pipecat.adapters.schemas.tools_schema import ToolsSchema

                mcp = MCPClient(server_params=mcp_params)
                mcp_tools = await mcp.register_tools(llm)
                all_tools.extend(mcp_tools.standard_tools)
                tools = ToolsSchema(standard_tools=all_tools)
                logger.info(f"MCP enabled: {len(mcp_tools.standard_tools)} tools from MCP server")
            except Exception as e:
                logger.warning(f"MCP setup failed: {e}")

        # Inject real-time Sui token data into context for portfolio building
        token_context = await fetch_sui_top_tokens(session)
        system_content = SYSTEM_PROMPT
        if token_context:
            system_content += f"\n\nCurrent Sui token data (use for portfolio advice):\n{token_context}"
        messages = [{"role": "system", "content": system_content}]
        context = LLMContext(messages=messages, tools=tools)
        # VAD tuned for noisy environments: higher confidence and min_volume reduce false triggers
        vad_confidence = float(os.getenv("VAD_CONFIDENCE", "0.75"))
        vad_stop_secs = float(os.getenv("VAD_STOP_SECS", "0.4"))
        vad_min_volume = float(os.getenv("VAD_MIN_VOLUME", "0.5"))
        vad_params = VADParams(
            confidence=vad_confidence,
            stop_secs=vad_stop_secs,
            min_volume=vad_min_volume,
        )
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                user_turn_strategies=UserTurnStrategies(
                    stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
                ),
                vad_analyzer=SileroVADAnalyzer(params=vad_params),
            ),
        )

        # Audio recording
        audio_buffer = AudioBufferProcessor()

        # Pipeline - assembled from reusable components
        pipeline = Pipeline([
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            audio_buffer,
            assistant_aggregator,
        ])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            enable_rtvi=True,
            observers=[
                WhiskerObserver(pipeline),
                *([TailObserver()] if _TAIL_AVAILABLE and TailObserver else []),
            ],
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("Client connected")
            await audio_buffer.start_recording()
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("Client disconnected")
            await task.cancel()

        @user_aggregator.event_handler("on_user_turn_stopped")
        async def on_user_turn_stopped(aggregator, strategy, message: UserTurnStoppedMessage):
            timestamp = f"[{message.timestamp}] " if message.timestamp else ""
            line = f"{timestamp}user: {message.content}"
            logger.info(f"Transcript: {line}")

        @assistant_aggregator.event_handler("on_assistant_turn_stopped")
        async def on_assistant_turn_stopped(aggregator, message: AssistantTurnStoppedMessage):
            timestamp = f"[{message.timestamp}] " if message.timestamp else ""
            line = f"{timestamp}assistant: {message.content}"
            logger.info(f"Transcript: {line}")

        @audio_buffer.event_handler("on_audio_data")
        async def on_audio_data(buffer, audio, sample_rate, num_channels):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recordings/merged_{timestamp}.wav"
            os.makedirs("recordings", exist_ok=True)
            await save_audio_file(audio, filename, sample_rate, num_channels)

        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point."""

    transport = None

    # Optional input noise reduction for noisy environments (requires pipecat-ai[rnnoise])
    audio_in_filter = None
    if os.getenv("AURAAI_NOISE_REDUCTION", "").strip().lower() == "rnnoise":
        try:
            from pipecat.audio.filters.rnnoise_filter import RNNoiseFilter

            audio_in_filter = RNNoiseFilter()
            logger.info("Noise reduction enabled (RNNoise)")
        except Exception as e:
            logger.warning("RNNoise filter not available (install pipecat-ai[rnnoise]): %s", e)

    match runner_args:
        case SmallWebRTCRunnerArguments():
            webrtc_connection: SmallWebRTCConnection = runner_args.webrtc_connection

            transport = SmallWebRTCTransport(
                webrtc_connection=webrtc_connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    audio_in_filter=audio_in_filter,
                ),
            )
        case _:
            logger.error(f"Unsupported runner arguments type: {type(runner_args)}")
            return

    await run_bot(transport)


if __name__ == "__main__":
    # Use run_server.py for full flow (DB init + JWT persistence)
    from run_server import main

    main()