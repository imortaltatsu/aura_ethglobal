"""Custom Pipecat runner entry point with JWT persistence and DB init.

Ensures:
- DB (including spawned_wallets) is initialized on startup
- JWT is persisted to jwt_sessions when client connects via POST /start
- Websocket/WebRTC subscription flow works with stored sessions
- WebRTC handler uses STUN (and optional TURN) from env so ICE can complete
  when client and server are on different networks (e.g. over SSH).
"""

import argparse
import asyncio
import json
import os

# Must run bot module so pipecat discovers bot()
import bot  # noqa: F401

# When __main__ is run_server, the runner's _get_bot_module() returns __main__ and expects
# .bot to be the callable. Here "bot" is the module; expose the real callable as __main__.bot.
import sys
sys.modules["__main__"].bot = bot.bot

import pipecat.runner.run as runner_module
from starlette.middleware.base import BaseHTTPMiddleware

_original_create_server_app = runner_module._create_server_app


def _inject_webrtc_ice_servers():
    """Patch SmallWebRTCRequestHandler so ICE servers are used when WEBRTC_ICE_SERVERS is set.

    Only applies when the env var is set, so default behavior (no ICE servers) is unchanged.
    For cross-network/SSH, set e.g. WEBRTC_ICE_SERVERS=stun:stun.l.google.com:19302
    """
    from pipecat.transports.smallwebrtc.connection import IceServer
    from pipecat.transports.smallwebrtc.request_handler import (
        ConnectionMode,
        SmallWebRTCRequestHandler,
    )

    _orig_init = SmallWebRTCRequestHandler.__init__

    def _patched_init(
        self,
        ice_servers=None,
        esp32_mode=False,
        host=None,
        connection_mode=ConnectionMode.MULTIPLE,
    ):
        if ice_servers is None:
            urls_str = os.getenv("WEBRTC_ICE_SERVERS", "").strip()
            if urls_str:
                urls = [u.strip() for u in urls_str.split(",") if u.strip()]
                ice_servers = [IceServer(urls=u) for u in urls]
        _orig_init(
            self,
            ice_servers=ice_servers,
            esp32_mode=esp32_mode,
            host=host,
            connection_mode=connection_mode,
        )

    SmallWebRTCRequestHandler.__init__ = _patched_init
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger


async def _persist_jwt_if_start(session_id: str | None, token: str | None) -> None:
    """Persist JWT to DB when session is created via /start."""
    if not session_id or not token:
        return
    try:
        from db import upsert_jwt_session

        await upsert_jwt_session(session_id=session_id, token=token)
    except Exception as e:
        logger.warning(f"JWT persistence failed: {e}")


class JWTPersistenceMiddleware(BaseHTTPMiddleware):
    """Persist JWT to DB when client connects via POST /start with Bearer token."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method != "POST" or request.url.path != "/start":
            return response

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return response

        token = auth[7:].strip()
        if not token:
            return response

        body = b""
        try:
            async for chunk in response.body_iterator:
                body += chunk
            data = json.loads(body)
            session_id = data.get("sessionId") if isinstance(data, dict) else None
            await _persist_jwt_if_start(session_id, token)
        except Exception as e:
            logger.warning(f"JWT persistence middleware: {e}")
        # Always return the collected body so the client gets sessionId; never return
        # the original response after consuming its body_iterator (would be empty).
        return Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
        )

async def _api_wallet_info():
    """GET /api/wallet-info: return wallet address and funding info for the client UI."""
    from tools import get_fund_wallet_info_data
    return await get_fund_wallet_info_data()


async def _api_address():
    """GET /api/address: return the global static wallet address only."""
    from tools import get_fund_wallet_info_data
    data = await get_fund_wallet_info_data()
    if data.get("error"):
        return {"address": None, "error": data["error"]}
    return {"address": data.get("address")}


async def _api_wallet_dashboard():
    """GET /api/wallet-dashboard: wallet info + balance + holdings for the client dashboard."""
    from tools import get_fund_wallet_info_data, get_wallet_balance_data
    info = await get_fund_wallet_info_data()
    if info.get("error") or not info.get("address"):
        return {**info, "holdings": [], "total_usd": 0.0}
    balance = await get_wallet_balance_data(info["address"])
    return {
        "address": info["address"],
        "network": info["network"],
        "faucet_url": info.get("faucet_url"),
        "instructions": info.get("instructions"),
        "error": info.get("error"),
        "holdings": balance.get("holdings", []),
        "total_usd": balance.get("total_usd", 0.0),
    }


def _patched_create_server_app(args: argparse.Namespace):
    app = _original_create_server_app(args)
    app.add_middleware(JWTPersistenceMiddleware)
    app.add_api_route("/api/wallet-info", _api_wallet_info, methods=["GET"])
    app.add_api_route("/api/address", _api_address, methods=["GET"])
    app.add_api_route("/api/wallet-dashboard", _api_wallet_dashboard, methods=["GET"])
    return app


def main():
    asyncio.run(__import__("db").init_db())
    _inject_webrtc_ice_servers()
    runner_module._create_server_app = _patched_create_server_app
    runner_module.main()


if __name__ == "__main__":
    main()
