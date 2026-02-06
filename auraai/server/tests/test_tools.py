#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Integration tests for tools: real Sui testnet RPC and DeFiLlama APIs (no mocks)."""
import json

import pytest

from tools import (
    get_fund_wallet_info_data,
    get_wallet_balance_data,
    get_current_time,
    get_current_date,
    analyze_portfolio,
    get_wallet_balance,
    get_fund_wallet_info,
)


@pytest.mark.asyncio
async def test_get_fund_wallet_info_data_real():
    """Real testnet: get_fund_wallet_info_data returns address from env/DB or error."""
    result = await get_fund_wallet_info_data()
    assert "address" in result
    assert "network" in result
    assert "error" in result
    assert "instructions" in result or result.get("error")
    if result["address"]:
        assert result["address"].startswith("0x")
        assert result["network"] in ("testnet", "mainnet")
    else:
        assert result["error"] is not None


@pytest.mark.asyncio
async def test_get_wallet_balance_data_real_global_wallet():
    """Real testnet: get_wallet_balance_data uses global wallet (env/DB); may error if none configured."""
    result = await get_wallet_balance_data()
    assert "address" in result
    assert "holdings" in result
    assert "total_usd" in result
    assert "error" in result
    if result["error"] is None:
        assert result["address"] is not None
        assert result["address"].startswith("0x")
        assert isinstance(result["holdings"], list)
        assert isinstance(result["total_usd"], (int, float))
    else:
        assert "wallet" in result["error"].lower() or "address" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_sui_token_prices_real():
    """Real DeFiLlama: get_sui_token_prices returns token list or error."""
    from tools import get_sui_token_prices
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    await get_sui_token_prices(params)
    assert len(callback_results) == 1
    data = callback_results[0]
    assert "tokens" in data
    assert "error" in data
    if data["error"] is None:
        assert isinstance(data["tokens"], list)


@pytest.mark.asyncio
async def test_analyze_portfolio_real():
    """Real DeFiLlama: analyze_portfolio with valid holdings returns allocations."""
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    holdings = json.dumps([{"symbol": "SUI", "amount": 10}, {"symbol": "USDC", "amount": 100}])
    await analyze_portfolio(params, holdings=holdings)
    assert len(callback_results) == 1
    data = callback_results[0]
    assert "total_usd" in data
    assert "allocations" in data
    assert "error" in data
    if data["error"] is None:
        assert data["total_usd"] >= 0
        assert len(data["allocations"]) == 2
        for a in data["allocations"]:
            assert "symbol" in a
            assert "allocation_pct" in a


@pytest.mark.asyncio
async def test_analyze_portfolio_invalid_json_returns_error():
    """Invalid JSON in holdings returns error (no network call needed)."""
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    await analyze_portfolio(params, holdings="not json")
    assert len(callback_results) == 1
    assert callback_results[0]["error"] is not None


@pytest.mark.asyncio
async def test_get_current_time_real():
    """get_current_time returns time in callback."""
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    await get_current_time(params, timezone="UTC")
    assert len(callback_results) == 1
    assert "time" in callback_results[0]
    assert "time_24h" in callback_results[0]
    assert callback_results[0]["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_get_current_date_real():
    """get_current_date returns date in callback."""
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    await get_current_date(params, timezone="America/New_York")
    assert len(callback_results) == 1
    assert "date" in callback_results[0]
    assert "weekday" in callback_results[0]


@pytest.mark.asyncio
async def test_get_wallet_balance_callback():
    """get_wallet_balance uses global wallet and invokes callback with balance data (real or error)."""
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    await get_wallet_balance(params)
    assert len(callback_results) == 1
    assert "holdings" in callback_results[0]
    assert "total_usd" in callback_results[0]


@pytest.mark.asyncio
async def test_get_fund_wallet_info_callback():
    """get_fund_wallet_info invokes callback with wallet info (real or error)."""
    from unittest.mock import MagicMock
    params = MagicMock()
    callback_results = []
    async def capture(result):
        callback_results.append(result)
    params.result_callback = capture
    await get_fund_wallet_info(params)
    assert len(callback_results) == 1
    assert "address" in callback_results[0]
    assert "error" in callback_results[0]
