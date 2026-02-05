#!/usr/bin/env python3
# Follows DipCoin SDK tutorials: https://github.com/dipcoinlab/dipcoin-amm-client-python/blob/main/docs/tutorials.md
# Run from server dir: uv run python examples/dipcoin_example.py

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dipcoin
from dipcoin.constants import CONTRACT_CONSTANTS, TESTNET_FAUCET
from dipcoin.exceptions import PoolNotFound


async def find_pool(client: dipcoin.DipcoinClient) -> None:
    """Tutorial: Finding a Pool."""
    coin_x_type = TESTNET_FAUCET["COIN_USDC"]
    coin_y_type = TESTNET_FAUCET["COIN_WSOL"]
    pool_id = await client.get_pool_id(coin_x_type, coin_y_type)
    if pool_id:
        print(f"Found pool: {pool_id}")
    else:
        print("No pool found for this pair")


async def exact_input_swap(client: dipcoin.DipcoinClient) -> None:
    """Tutorial: Exact Input Swap (keyword args, check result.status)."""
    coin_in_type = TESTNET_FAUCET["COIN_USDC"]
    coin_out_type = TESTNET_FAUCET["COIN_WSOL"]
    amount_in = 100000  # raw units
    result = await client.swap_exact_in(
        coin_in_type=coin_in_type,
        coin_out_type=coin_out_type,
        amount_in=amount_in,
        slippage=0.005,
    )
    if result.status:
        print(f"Swap successful! Transaction ID: {result.digest}")
        print(f"  Explorer: https://suiexplorer.com/txblock/{result.digest}?network=testnet")
    else:
        print(f"Swap failed: {result.error}")


def _is_network_error(e: BaseException) -> bool:
    msg = str(e).lower()
    return (
        "errno -5" in msg
        or "no address associated with hostname" in msg
        or "name or service not known" in msg
        or "connection" in msg
        or "transport" in msg
    )


async def main() -> None:
    if "testnet" not in CONTRACT_CONSTANTS:
        print("CONTRACT_CONSTANTS has no testnet; SDK may be outdated.")
        return
    try:
        client = dipcoin.DipcoinClient(network="testnet")
    except Exception as e:
        if _is_network_error(e):
            print(
                "Cannot reach Sui network (DNS/firewall). "
                "Run where outbound HTTPS is allowed, or set DIPCOIN_SUI_RPC to an alt RPC."
            )
            sys.exit(1)
        raise
    try:
        await find_pool(client)
        # Uncomment to run a real swap (uses pysui active address):
        # await exact_input_swap(client)
    except PoolNotFound as e:
        print(f"Pool not found: {e}")
    except ValueError as e:
        print(f"Invalid input: {e}")
    except Exception as e:
        if _is_network_error(e):
            print("Network error during request. Check connectivity or use DIPCOIN_SUI_RPC.")
            sys.exit(1)
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
