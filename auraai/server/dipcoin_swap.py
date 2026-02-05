#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""DipCoin AMM swap integration via dipcoin-amm-client-python.

SDK: https://github.com/dipcoinlab/dipcoin-amm-client-python
Tutorials: https://github.com/dipcoinlab/dipcoin-amm-client-python/blob/main/docs/tutorials.md

Install: pip install 'dipcoin @ git+https://github.com/dipcoinlab/dipcoin-amm-client-python.git'
Note: dipcoin pulls in pysui; uses pysui config for signing (active address = server wallet).
"""

from __future__ import annotations

import os
from typing import Any

# Coin type mapping: symbol -> (coin_type, decimals). Uses SDK constants like the repo example.
# https://github.com/dipcoinlab/dipcoin-amm-client-python/blob/main/examples/example.py
SUI_COIN_TYPE = "0x2::sui::SUI"
SUI_DECIMALS = 9
USDC_DECIMALS = 6

def _get_coin_types() -> dict[str, tuple[str | None, int]]:
    out: dict[str, tuple[str | None, int]] = {
        "SUI": (SUI_COIN_TYPE, SUI_DECIMALS),
        "USDC": (None, USDC_DECIMALS),
    }
    try:
        from dipcoin.constants import CONTRACT_CONSTANTS, TESTNET_FAUCET
        if "testnet" in CONTRACT_CONSTANTS:
            out["USDC"] = (TESTNET_FAUCET["COIN_USDC"], USDC_DECIMALS)
            out["WSOL"] = (TESTNET_FAUCET["COIN_WSOL"], 9)
            out["WETH"] = (TESTNET_FAUCET["COIN_WETH"], 9)
            out["CETUS"] = (TESTNET_FAUCET["COIN_CETUS"], 9)
    except ImportError:
        pass
    return out


COIN_TYPES = _get_coin_types()


def _symbol_to_coin_type(symbol: str) -> tuple[str, int]:
    s = (symbol or "").strip().upper()
    if s not in COIN_TYPES:
        raise ValueError(f"Unknown token symbol: {symbol}. Supported: {list(COIN_TYPES.keys())}")
    ct, dec = COIN_TYPES[s]
    if ct is None:
        raise ValueError(f"Coin type for {symbol} not configured (missing SDK constants).")
    return ct, dec


def _human_to_raw(amount: float, decimals: int) -> int:
    if amount <= 0:
        raise ValueError("Amount must be positive")
    return int(amount * (10**decimals))


async def execute_dipcoin_swap(
    coin_in_symbol: str,
    coin_out_symbol: str,
    amount_in_human: float,
    slippage: float = 0.005,
    address: str | None = None,
) -> dict[str, Any]:
    """Execute a swap on DipCoin AMM. Uses pysui config; active address must match server wallet.

    Returns dict with keys: success (bool), digest (str), error (str | None), message (str).
    """
    from tools import get_fund_wallet_info_data
    from dipcoin_client import is_testnet, get_sui_rpc

    result: dict[str, Any] = {"success": False, "digest": "", "error": None, "message": ""}

    # Resolve wallet address
    if not address or not address.strip():
        info = await get_fund_wallet_info_data()
        address = info.get("address")
        if info.get("error") or not address:
            result["error"] = info.get("error") or "No server wallet configured."
            result["message"] = "Configure a wallet first (spawn or set SERVER_WALLET_ADDRESS)."
            return result

    network = "testnet" if is_testnet() else "mainnet"

    try:
        import dipcoin
    except ImportError:
        result["error"] = "dipcoin_not_installed"
        result["message"] = (
            "DipCoin swap requires the dipcoin package from "
            "https://github.com/dipcoinlab/dipcoin-amm-client-python — "
            "pip install 'dipcoin @ git+https://github.com/dipcoinlab/dipcoin-amm-client-python.git'"
        )
        return result

    # CONTRACT_CONSTANTS may only have testnet in the SDK
    if network != "testnet":
        result["error"] = "mainnet_not_supported"
        result["message"] = "DipCoin swap is currently supported on testnet only."
        return result

    try:
        coin_in_type, dec_in = _symbol_to_coin_type(coin_in_symbol)
        coin_out_type, _ = _symbol_to_coin_type(coin_out_symbol)
        amount_in_raw = _human_to_raw(amount_in_human, dec_in)
    except ValueError as e:
        result["error"] = "invalid_params"
        result["message"] = str(e)
        return result

    try:
        # Use alt RPC from env so dipcoin SDK queries (get_pool_id, etc.) hit the same endpoint
        import dipcoin.constants as _dc_constants
        _dc_constants.NODE_RPC = {**_dc_constants.NODE_RPC, network: get_sui_rpc()}
        # Same pattern as repo example: https://github.com/dipcoinlab/dipcoin-amm-client-python/blob/main/examples/example.py
        client = dipcoin.DipcoinClient(network=network)
    except OSError:
        # DNS or network unreachable (e.g. errno -5: No address associated with hostname)
        result["error"] = "network_error"
        result["message"] = (
            "Server cannot reach the Sui network (DNS or firewall). "
            "You can still swap SUI to USDC using the DeepBook or SuiSwap links in the wallet panel."
        )
        return result
    except Exception as e:
        err_str = str(e).lower()
        if "address associated with hostname" in err_str or "name or service not known" in err_str or "errno -5" in err_str:
            result["error"] = "network_error"
            result["message"] = (
                "Server cannot reach the Sui network (DNS or firewall). "
                "You can still swap SUI to USDC using the DeepBook or SuiSwap links in the wallet panel."
            )
        else:
            result["error"] = "client_init"
            result["message"] = f"Could not create DipCoin client: {e}. Ensure pysui is configured (sui client active-address)."
        return result

    # Ensure active address matches our server wallet so we sign with the right key
    active = getattr(client.client.config, "active_address", None) or getattr(
        getattr(client.client, "config", None), "active_address", None
    )
    if active and str(active) != address:
        result["error"] = "address_mismatch"
        result["message"] = (
            f"pysui active address ({active}) does not match server wallet ({address}). "
            "Set pysui to use the server wallet: sui client switch --address " + address
        )
        return result

    try:
        from dipcoin.exceptions import PoolNotFound
    except ImportError:
        PoolNotFound = type("PoolNotFound", (Exception,), {})  # noqa: no cover
    try:
        # Tutorial style: https://github.com/dipcoinlab/dipcoin-amm-client-python/blob/main/docs/tutorials.md
        tx_resp = await client.swap_exact_in(
            coin_in_type=coin_in_type,
            coin_out_type=coin_out_type,
            amount_in=amount_in_raw,
            slippage=slippage,
        )
    except PoolNotFound:
        result["error"] = "pool_not_found"
        result["message"] = f"No pool for {coin_in_symbol}/{coin_out_symbol}. Check token pair."
        return result
    except Exception as e:
        result["error"] = "swap_failed"
        result["message"] = str(e)
        return result

    if getattr(tx_resp, "status", False):
        result["success"] = True
        result["digest"] = getattr(tx_resp, "digest", "") or ""
        result["message"] = f"Swap submitted. Digest: {result['digest']}"
    else:
        result["error"] = "swap_failed"
        result["message"] = getattr(tx_resp, "error", None) or "Transaction failed."

    return result
