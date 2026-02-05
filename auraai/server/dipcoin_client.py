"""DipCoin/Sui DeFi data and on-chain helpers.

RPC is controlled by DIPCOIN_SUI_RPC (optional) and DIPCOIN_TESTNET.
- Default testnet: https://fullnode.testnet.sui.io
- Default mainnet: https://fullnode.mainnet.sui.io
- Alt RPC: set DIPCOIN_SUI_RPC to any Sui JSON-RPC endpoint.
  NodeInfra (Mainnet & Testnet): https://docs.nodeinfra.com/
  e.g. testnet: https://sui-testnet.nodeinfra.com
       mainnet: https://sui-mainnet.nodeinfra.com

pysui/DipCoin swaps use GraphQL; official testnet GraphQL:
  https://graphql.testnet.sui.io/graphql
"""

import os

# Default Sui JSON-RPC endpoints (used when DIPCOIN_SUI_RPC is not set)
SUI_MAINNET_RPC = "https://fullnode.mainnet.sui.io"
SUI_TESTNET_RPC = "https://fullnode.testnet.sui.io"

# Official Sui GraphQL (for pysui/sui client config when using testnet)
SUI_TESTNET_GRAPHQL = "https://graphql.testnet.sui.io/graphql"
SUI_MAINNET_GRAPHQL = "https://graphql.mainnet.sui.io/graphql"


def get_sui_rpc() -> str:
    """Return Sui RPC URL. Uses DIPCOIN_SUI_RPC if set, else default for testnet/mainnet."""
    rpc = os.getenv("DIPCOIN_SUI_RPC", "").strip()
    if rpc:
        return rpc.rstrip("/")
    use_testnet = os.getenv("DIPCOIN_TESTNET", "true").lower() in ("1", "true", "yes")
    return SUI_TESTNET_RPC if use_testnet else SUI_MAINNET_RPC


def is_testnet() -> bool:
    """True if using Sui testnet."""
    return "testnet" in get_sui_rpc().lower()
