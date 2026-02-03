# aura_ethglobal

Voice AI agent (Pipecat) with Sui wallet and DipCoin AMM swaps — EthGlobal project.

- **auraai/** — Voice bot (STT → LLM → TTS), WebRTC client, wallet UI, Sui testnet integration
- **sesame-service/** — Sesame service

## Quick start

```bash
cd auraai/server
cp .env.example .env   # set DIPCOIN_SUI_RPC, SERVER_WALLET_ADDRESS, etc.
uv sync
uv run python run_server.py
```

See [auraai/README.md](auraai/README.md) for full setup.
