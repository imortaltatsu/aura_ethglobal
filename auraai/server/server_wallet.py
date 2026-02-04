"""Spawn Sui wallets and store in DB."""

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from db import upsert_server_wallet, upsert_spawned_wallet

SUI_AVAILABLE = False
try:
    from pysui.sui.sui_keys import SuiKeyPair

    SUI_AVAILABLE = True
except ImportError:
    pass

# Sui address from Ed25519: BLAKE2b(0x00 || pubkey_32)[:32], then 0x + hex
SUI_ED25519_FLAG = b"\x00"


def _get_fernet() -> Fernet:
    secret = os.getenv("AURAAI_WALLET_ENCRYPTION_KEY", "auraai-default-key-change-in-prod").encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=b"auraai_wallet", iterations=100000
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)


def _sui_address_from_ed25519_public_key(pubkey_bytes: bytes) -> str:
    """Derive Sui address from 32-byte Ed25519 public key (Sui spec: flag 0x00 + pubkey, BLAKE2b)."""
    digest = hashlib.blake2b(SUI_ED25519_FLAG + pubkey_bytes, digest_size=32).digest()
    return "0x" + digest.hex()


def _spawn_wallet_native(chain: str, label: str | None) -> tuple[str, str]:
    """Create Sui keypair using cryptography only (no pysui). Returns (address, encrypted_storage)."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    addr = _sui_address_from_ed25519_public_key(pub_bytes)
    # Store as v1:base64(privkey) so get_keypair_for_address can detect native format
    storage = "v1:" + base64.b64encode(priv_bytes).decode()
    f = _get_fernet()
    enc = f.encrypt(storage.encode()).decode()
    return addr, enc


async def spawn_wallet(chain: str = "sui", label: str | None = None) -> dict:
    """Create a new Sui keypair, encrypt and store in DB. Returns address and funding info."""
    from dipcoin_client import is_testnet

    if SUI_AVAILABLE:
        kp = SuiKeyPair()
        addr = str(kp.to_address())
        f = _get_fernet()
        enc = f.encrypt(kp.export_keypair().encode()).decode()
    else:
        addr, enc = _spawn_wallet_native(chain, label)

    await upsert_spawned_wallet(
        address=addr,
        encrypted_key=enc,
        chain=chain,
        label=label or "",
    )
    # Persist as global server wallet so the key survives restarts and is used for signing
    await upsert_server_wallet(address=addr, encrypted_key=enc, chain=chain)

    faucet = "https://faucet.sui.io" if is_testnet() else None

    return {
        "address": addr,
        "chain": chain,
        "network": "testnet" if is_testnet() else "mainnet",
        "faucet_url": faucet,
        "instructions": f"Visit {faucet} for test SUI, then send to {addr}" if faucet else f"Send SUI to {addr}",
    }


async def get_keypair_for_address(address: str, chain: str = "sui"):
    """Load decrypted keypair for an address. Checks server_wallet first (persistent global), then spawned_wallets. Returns SuiKeyPair or None."""
    if not SUI_AVAILABLE:
        return None

    from db import get_connection, get_server_wallet

    # Prefer persistent global wallet key so it survives restarts
    server_row = await get_server_wallet(chain)
    if server_row and (server_row.get("address") or server_row["address"]) == address:
        enc_key = server_row.get("encrypted_key") or server_row["encrypted_key"]
    else:
        enc_key = None
        DB_PATH = os.getenv("AURAAI_DB_PATH", str(Path(__file__).resolve().parent / "data" / "auraai.db"))
        DB_BACKEND = os.getenv("AURAAI_DB_BACKEND", "sqlite").lower()
        if DB_BACKEND == "duckdb":
            import duckdb
            conn = duckdb.connect(DB_PATH)
            row = conn.execute(
                "SELECT encrypted_key FROM spawned_wallets WHERE address = ?",
                [address],
            ).fetchone()
            conn.close()
            enc_key = row[0] if row else None
        else:
            conn = await get_connection()
            cursor = await conn.execute(
                "SELECT encrypted_key FROM spawned_wallets WHERE address = ?",
                (address,),
            )
            row = await cursor.fetchone()
            await conn.close()
            enc_key = row["encrypted_key"] if row else None

    if not enc_key:
        return None

    f = _get_fernet()
    dec = f.decrypt(enc_key.encode()).decode()
    # Wallets created with _spawn_wallet_native (no pysui) use "v1:" prefix; no signing support without pysui
    if dec.startswith("v1:"):
        return None
    return SuiKeyPair.from_b64(dec)
