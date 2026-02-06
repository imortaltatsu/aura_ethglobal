#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Tests for dipcoin_swap (symbol mapping, amount conversion, execute paths)."""
import pytest

from dipcoin_swap import (
    _symbol_to_coin_type,
    _human_to_raw,
    execute_dipcoin_swap,
    SUI_COIN_TYPE,
    SUI_DECIMALS,
    USDC_DECIMALS,
)


def test_symbol_to_coin_type_sui():
    """SUI maps to native coin type and 9 decimals."""
    ct, dec = _symbol_to_coin_type("SUI")
    assert ct == SUI_COIN_TYPE
    assert dec == SUI_DECIMALS


def test_symbol_to_coin_type_case_insensitive():
    """Symbol is normalized to uppercase for lookup."""
    ct, dec = _symbol_to_coin_type("sui")
    assert ct == SUI_COIN_TYPE
    assert dec == SUI_DECIMALS


def test_symbol_to_coin_type_unknown_raises():
    """Unknown symbol raises ValueError."""
    with pytest.raises(ValueError, match="Unknown token symbol"):
        _symbol_to_coin_type("UNKNOWN")
    with pytest.raises(ValueError, match="Unknown"):
        _symbol_to_coin_type("BTC")


def test_human_to_raw_positive():
    """Human amount converts to raw with correct decimals."""
    assert _human_to_raw(1.0, 9) == 1_000_000_000
    assert _human_to_raw(0.5, 9) == 500_000_000
    assert _human_to_raw(100.0, 6) == 100_000_000
    assert _human_to_raw(1.5, 6) == 1_500_000


def test_human_to_raw_zero_raises():
    """Zero amount raises ValueError."""
    with pytest.raises(ValueError, match="positive"):
        _human_to_raw(0, 9)


def test_human_to_raw_negative_raises():
    """Negative amount raises ValueError."""
    with pytest.raises(ValueError, match="positive"):
        _human_to_raw(-1.0, 9)


@pytest.mark.asyncio
async def test_execute_dipcoin_swap_real_no_wallet():
    """Real: when global config has no server wallet, returns error (no mocks, no env override)."""
    import os
    if os.environ.get("SERVER_WALLET_ADDRESS", "").strip():
        pytest.skip("Global wallet is set; skip 'no wallet' test")
    result = await execute_dipcoin_swap("SUI", "USDC", 1.0)
    assert result.get("success") is False
    assert result.get("error") or "wallet" in (result.get("message") or "").lower()


@pytest.mark.asyncio
async def test_execute_dipcoin_swap_real_invalid_symbol():
    """Real: invalid coin symbol returns invalid_params; uses global wallet."""
    result = await execute_dipcoin_swap("INVALID", "USDC", 1.0)
    assert result.get("success") is False
    assert result.get("error") == "invalid_params"


@pytest.mark.asyncio
async def test_execute_dipcoin_swap_real_mainnet_not_supported(monkeypatch):
    """Real: on mainnet (DIPCOIN_TESTNET=false), returns mainnet_not_supported; uses global wallet."""
    monkeypatch.setenv("DIPCOIN_TESTNET", "false")
    result = await execute_dipcoin_swap("SUI", "USDC", 1.0)
    assert result.get("success") is False
    assert result.get("error") == "mainnet_not_supported"
    assert "testnet" in (result.get("message") or "").lower()


@pytest.mark.asyncio
async def test_execute_dipcoin_swap_real_testnet_integration():
    """Real testnet: execute_dipcoin_swap using global wallet; may succeed or fail with tx error.
    Run with: pytest tests/test_dipcoin_swap.py::test_execute_dipcoin_swap_real_testnet_integration -v -s
    to see the full response (digest, message, etc.) in the terminal.
    Skips when the environment cannot reach the Sui network (e.g. sandbox, no outbound).
    """
    result = await execute_dipcoin_swap("SUI", "USDC", 0.001)
    import json
    print("\n--- execute_dipcoin_swap result ---")
    print(json.dumps(result, indent=2))
    if result.get("success") and result.get("digest"):
        print(f"\nExplorer: https://suiexplorer.com/txblock/{result['digest']}?network=testnet")
    print("---\n")
    # Skip when we never reached the chain (network/DNS blocked); only pass when we got a real response
    if result.get("error") == "network_error":
        pytest.skip(
            "Environment cannot reach Sui network (DNS/firewall). "
            "Run this test where outbound HTTPS to fullnode.testnet.sui.io is allowed."
        )
    if result.get("error") == "dipcoin_not_installed":
        pytest.skip("dipcoin package not installed")
    assert "success" in result
    assert "error" in result or "message" in result
    if result.get("success"):
        assert result.get("digest") or result.get("message")
    else:
        assert result.get("error") or result.get("message")
