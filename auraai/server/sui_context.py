#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Sui top token data for context (DeFiLlama coins.llama.fi)."""

import os

# Default Sui tokens: native + stablecoins + ecosystem (Llama format: chain:address)
# SUI, USDC, CETUS (Cetus DEX), NAVX (Navi), SCA (Scallop)
DEFAULT_SUI_TOKEN_IDS = [
    "sui:0x2::sui::SUI",
    "sui:0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
    "sui:0x06864a6f921804860930db6ddbe2e16acdf8504495ea7481637a1c8b9a8fe54b::cetus::CETUS",
    "sui:0xa99b8952d4f7d947ea77fe0ecdcc9e5fc0bcab2841d6e2a5aa00c3044e5544b5::navx::NAVX",
    "sui:0x7016aae72cfc67f2fadf55769c0a7dd54291a583b63051a5ed71081cce836ac6::sca::SCA",
]

COINS_LLAMA_URL = "https://coins.llama.fi/prices/current"


async def fetch_sui_top_tokens(aiohttp_session) -> str:
    """Fetch top Sui token prices from DeFiLlama and return a formatted string for context."""
    raw = os.getenv("SUI_TOKEN_IDS", "").strip()
    token_ids = [t.strip() for t in raw.split(",") if t.strip()] if raw else DEFAULT_SUI_TOKEN_IDS
    ids_param = ",".join(token_ids)
    url = f"{COINS_LLAMA_URL}/{ids_param}"

    try:
        async with aiohttp_session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
    except Exception:
        return ""

    coins = data.get("coins", {})
    if not coins:
        return ""

    lines = ["Sui tokens (native, stablecoins, ecosystem) USD approx:"]
    for coin_id, info in coins.items():
        symbol = info.get("symbol", "?")
        price = info.get("price")
        if price is not None:
            if price >= 1:
                pstr = f"${price:,.2f}"
            elif price >= 0.01:
                pstr = f"${price:.4f}"
            else:
                pstr = f"${price:.6f}"
            lines.append(f"  {symbol}: {pstr}")

    return "\n".join(lines) if len(lines) > 1 else ""


DEFILLAMA_PROTOCOLS = "https://api.llama.fi/protocols"


async def fetch_sui_defi_context(aiohttp_session) -> str:
    """Fetch Sui DeFi TVL and trend from DeFiLlama protocols."""
    try:
        async with aiohttp_session.get(DEFILLAMA_PROTOCOLS, timeout=12) as resp:
            if resp.status != 200:
                return ""
            protocols = await resp.json()
    except Exception:
        return ""

    sui_tvl = 0.0
    sui_change_1d = 0.0
    for p in protocols:
        if "Sui" not in (p.get("chains") or []):
            continue
        ctvl = p.get("chainTvls") or {}
        stvl = ctvl.get("Sui") or 0
        if stvl and stvl > 0:
            sui_tvl += float(stvl)
        chg = p.get("change_1d")
        if chg is not None:
            sui_change_1d = chg

    if sui_tvl <= 0:
        return ""

    lines = ["Sui DeFi (TVL trend):", f"  Sui chain TVL: ${sui_tvl/1e9:.2f}B"]
    if sui_change_1d != 0:
        direction = "up" if sui_change_1d > 0 else "down"
        lines.append(f"  TVL 1d: {direction} {abs(sui_change_1d):.1f}%")
    return "\n".join(lines)
