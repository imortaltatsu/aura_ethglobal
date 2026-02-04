#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Tools (function calling) for the voice agent."""

import datetime
import os
from zoneinfo import ZoneInfo

import aiohttp
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams


async def get_current_time(params: FunctionCallParams, timezone: str = "UTC") -> None:
    """Get the current time.

    Args:
        timezone: IANA timezone name, e.g. "America/New_York", "Europe/London", or "UTC".
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.datetime.now(tz)
    result = {
        "time": now.strftime("%I:%M %p"),
        "time_24h": now.strftime("%H:%M"),
        "timezone": str(tz),
    }
    await params.result_callback(result)


async def get_sui_token_prices(params: FunctionCallParams) -> None:
    """Get current Sui token prices in USD for portfolio building.

    Returns prices for top Sui tokens (SUI, USDC, etc.) from DeFiLlama.
    Use this when the user wants to build a portfolio or compare token values.
    """
    from sui_context import COINS_LLAMA_URL, DEFAULT_SUI_TOKEN_IDS

    raw = os.getenv("SUI_TOKEN_IDS", "").strip()
    token_ids = [t.strip() for t in raw.split(",") if t.strip()] if raw else DEFAULT_SUI_TOKEN_IDS
    ids_param = ",".join(token_ids)
    url = f"{COINS_LLAMA_URL}/{ids_param}"

    result = {"tokens": [], "error": None}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    result["error"] = "Could not fetch token prices"
                    await params.result_callback(result)
                    return
                data = await resp.json()
    except Exception as e:
        result["error"] = str(e)
        await params.result_callback(result)
        return

    coins = data.get("coins", {})
    for coin_id, info in coins.items():
        symbol = info.get("symbol", "?")
        price = info.get("price")
        decimals = info.get("decimals", 9)
        if price is not None:
            result["tokens"].append({"symbol": symbol, "price_usd": round(price, 6), "decimals": decimals})

    await params.result_callback(result)


async def analyze_portfolio(
    params: FunctionCallParams,
    holdings: str,
) -> None:
    """Analyze a crypto portfolio from holdings and current prices.

    Args:
        holdings: JSON array of {symbol, amount} e.g. [{\"symbol\":\"SUI\",\"amount\":100},{\"symbol\":\"USDC\",\"amount\":500}]
    """
    import json

    from sui_context import COINS_LLAMA_URL, DEFAULT_SUI_TOKEN_IDS

    result = {"total_usd": 0, "allocations": [], "error": None}
    try:
        h = json.loads(holdings)
        if not isinstance(h, list) or len(h) == 0:
            result["error"] = "Holdings must be a non-empty JSON array"
            await params.result_callback(result)
            return
    except json.JSONDecodeError as e:
        result["error"] = str(e)
        await params.result_callback(result)
        return

    raw = os.getenv("SUI_TOKEN_IDS", "").strip()
    token_ids = [t.strip() for t in raw.split(",") if t.strip()] if raw else DEFAULT_SUI_TOKEN_IDS
    url = f"{COINS_LLAMA_URL}/{','.join(token_ids)}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    result["error"] = "Could not fetch prices"
                    await params.result_callback(result)
                    return
                data = await resp.json()
    except Exception as e:
        result["error"] = str(e)
        await params.result_callback(result)
        return

    prices = {i.get("symbol", "?"): (i.get("price") or 0) for _, i in data.get("coins", {}).items()}
    total = 0.0
    items = []
    for item in h:
        sym = str(item.get("symbol", "")).upper()
        amt = float(item.get("amount", 0))
        price = prices.get(sym, 0)
        val = amt * price
        total += val
        items.append({"symbol": sym, "amount": amt, "price_usd": round(price, 6), "value_usd": round(val, 2)})

    for i in items:
        pct = (i["value_usd"] / total * 100) if total > 0 else 0
        i["allocation_pct"] = round(pct, 1)

    result["total_usd"] = round(total, 2)
    result["allocations"] = items
    await params.result_callback(result)


SUI_TESTNET_FAUCET = "https://faucet.sui.io"


async def spawn_wallet(params: FunctionCallParams, label: str = "") -> None:
    """Spawn a new Sui wallet and store it in the DB.

    Use when the user wants to create a new wallet for trading or receiving funds.
    Returns the address and funding instructions.
    """
    from server_wallet import spawn_wallet as _spawn_wallet

    result = await _spawn_wallet(chain="sui", label=label or None)
    await params.result_callback(result)


async def get_wallet_balance_data(address: str | None = None) -> dict:
    """Return wallet balance and holdings for an address (for API or tool).

    Uses same address resolution as get_wallet_balance: env, server_wallet, latest spawned.
    Returns dict with address, network, holdings, total_usd, error.
    """
    from db import get_server_wallet, get_latest_spawned_wallet
    from dipcoin_client import get_sui_rpc, is_testnet

    result: dict = {"address": None, "network": "testnet" if is_testnet() else "mainnet", "holdings": [], "total_usd": 0.0, "error": None}

    if not address or not address.strip():
        addr = os.getenv("SERVER_WALLET_ADDRESS", "").strip()
        if not addr:
            spawned = await get_latest_spawned_wallet("sui")
            if spawned:
                addr = spawned.get("address")
        if not addr:
            row = await get_server_wallet("sui")
            if row:
                addr = row.get("address") or row["address"]
        address = addr

    if not address or not address.strip():
        result["error"] = "No wallet address. Provide an address or configure SERVER_WALLET_ADDRESS."
        return result

    result["address"] = address

    rpc = get_sui_rpc()
    payload = {"jsonrpc": "2.0", "id": 1, "method": "suix_getAllBalances", "params": [address]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    result["error"] = f"RPC error: {resp.status}"
                    return result
                data = await resp.json()
    except Exception as e:
        result["error"] = str(e)
        return result

    err = data.get("error")
    if err:
        result["error"] = err.get("message", str(err))
        return result

    balances = data.get("result") or []
    if not balances:
        result["holdings"] = []
        result["total_usd"] = 0.0
        return result

    def coin_type_to_symbol(coin_type: str) -> str:
        parts = coin_type.split("::")
        return parts[-1] if parts else "?"

    def decimals_for_coin_type(coin_type: str) -> int:
        ct = (coin_type or "").lower()
        if "usdc" in ct or "usdt" in ct:
            return 6
        return 9

    holdings_raw = []
    for b in balances:
        coin_type = b.get("coinType", "")
        total = b.get("totalBalance", "0")
        dec = decimals_for_coin_type(coin_type)
        try:
            amt = int(total) / (10**dec)
        except (ValueError, TypeError):
            amt = 0
        symbol = coin_type_to_symbol(coin_type)
        holdings_raw.append({"symbol": symbol, "amount": amt, "coin_type": coin_type})

    from sui_context import COINS_LLAMA_URL, DEFAULT_SUI_TOKEN_IDS

    raw = os.getenv("SUI_TOKEN_IDS", "").strip()
    token_ids = [t.strip() for t in raw.split(",") if t.strip()] if raw else DEFAULT_SUI_TOKEN_IDS
    ids_param = ",".join(token_ids)
    url = f"{COINS_LLAMA_URL}/{ids_param}"
    prices = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    for _, info in (d.get("coins") or {}).items():
                        sym = info.get("symbol", "?")
                        p = info.get("price")
                        if p is not None:
                            prices[sym] = p
    except Exception:
        pass

    total_usd = 0.0
    items = []
    for h in holdings_raw:
        sym = h["symbol"].upper()
        amt = h["amount"]
        price = prices.get(sym, 0)
        val = amt * price
        total_usd += val
        items.append({"symbol": sym, "amount": round(amt, 6), "price_usd": round(price, 6), "value_usd": round(val, 2)})

    result["holdings"] = items
    result["total_usd"] = round(total_usd, 2)
    return result


async def get_wallet_balance(
    params: FunctionCallParams,
    address: str | None = None,
) -> None:
    """Get wallet balance and holdings for an address, with USD values.

    Use when the user wants to see wallet balance, holdings, or portfolio value.
    If address is not provided, uses the server wallet (or latest spawned wallet).
    Returns holdings with amounts and approximate USD value.
    """
    result = await get_wallet_balance_data(address)
    await params.result_callback(result)


async def get_fund_wallet_info_data() -> dict:
    """Return server wallet address and funding info (for API or tool).

    Uses a global static address priority: (1) SERVER_WALLET_ADDRESS env,
    (2) server_wallet row in DB, (3) latest spawned wallet.
    """
    from db import get_server_wallet, get_latest_spawned_wallet
    from dipcoin_client import is_testnet

    result = {"address": None, "network": "testnet" if is_testnet() else "mainnet", "faucet_url": None, "instructions": None, "error": None}

    # 1) Global static: env
    addr = os.getenv("SERVER_WALLET_ADDRESS", "").strip()
    # 2) Server wallet in DB (single canonical row)
    if not addr:
        row = await get_server_wallet("sui")
        if row:
            addr = row.get("address") or row["address"]
    # 3) Fallback: latest spawned
    if not addr:
        spawned = await get_latest_spawned_wallet("sui")
        if spawned:
            addr = spawned.get("address")

    if not addr:
        result["error"] = "No server wallet configured. Set SERVER_WALLET_ADDRESS in env or run wallet setup."
        return result

    result["address"] = addr
    if is_testnet():
        result["faucet_url"] = SUI_TESTNET_FAUCET
        result["instructions"] = f"Visit {SUI_TESTNET_FAUCET} to get test SUI, then send to {addr}"
    else:
        result["instructions"] = f"Send SUI or tokens to {addr}"

    return result


async def get_fund_wallet_info(params: FunctionCallParams) -> None:
    """Get the server wallet address and funding instructions.

    Use when the user wants to fund the wallet, get the deposit address, or add funds.
    Uses global static address: SERVER_WALLET_ADDRESS env, then server wallet in DB, then latest spawned.
    On testnet, includes the Sui faucet URL.
    """
    result = await get_fund_wallet_info_data()
    await params.result_callback(result)


async def dipcoin_swap(
    params: FunctionCallParams,
    coin_in: str,
    coin_out: str,
    amount_in: float,
    slippage: float = 0.005,
) -> None:
    """Swap tokens on DipCoin AMM (Sui testnet).

    Use when the user wants to swap or buy tokens (e.g. SUI to USDC, USDC to SUI).
    Requires the dipcoin package and pysui active address set to the server wallet.

    Args:
        coin_in: Input token symbol (e.g. SUI, USDC, WSOL).
        coin_out: Output token symbol.
        amount_in: Amount of input token (human-readable, e.g. 1.0 for 1 SUI).
        slippage: Max slippage as decimal (default 0.005 = 0.5%).
    """
    from dipcoin_swap import execute_dipcoin_swap

    result = await execute_dipcoin_swap(
        coin_in_symbol=coin_in,
        coin_out_symbol=coin_out,
        amount_in_human=amount_in,
        slippage=slippage,
    )
    await params.result_callback(result)


async def get_current_date(params: FunctionCallParams, timezone: str = "UTC") -> None:
    """Get today's date.

    Args:
        timezone: IANA timezone name, e.g. "America/New_York", "Europe/London", or "UTC".
    """
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.date.today()
    result = {
        "date": today.strftime("%A, %B %d, %Y"),
        "weekday": today.strftime("%A"),
        "timezone": str(tz),
    }
    await params.result_callback(result)


def get_tools_schema() -> ToolsSchema:
    """Build the tools schema for the LLM context."""
    return ToolsSchema(
        standard_tools=[
            get_current_time,
            get_current_date,
            get_sui_token_prices,
            analyze_portfolio,
            spawn_wallet,
            get_fund_wallet_info,
            get_wallet_balance,
            dipcoin_swap,
        ]
    )
