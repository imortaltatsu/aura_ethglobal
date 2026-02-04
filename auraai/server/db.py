"""Local DB for JWT sessions, server wallet, and portfolio data.

Uses SQLite by default. Set AURAAI_DB_BACKEND=duckdb for DuckDB.
"""

import hashlib
import os
import time
from pathlib import Path
from typing import Optional

DB_PATH = os.getenv("AURAAI_DB_PATH", str(Path(__file__).resolve().parent / "data" / "auraai.db"))
DB_BACKEND = os.getenv("AURAAI_DB_BACKEND", "sqlite").lower()


async def get_connection():
    """Get async DB connection (SQLite or DuckDB)."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        return conn
    import aiosqlite
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db() -> None:
    """Create tables if they don't exist."""
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jwt_sessions (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                user_id TEXT,
                token_hash TEXT NOT NULL,
                expires_at INTEGER,
                created_at INTEGER NOT NULL
            );
                CREATE TABLE IF NOT EXISTS server_wallet (
                    id INTEGER PRIMARY KEY,
                    address TEXT NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    chain TEXT DEFAULT 'sui',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(chain)
                );
                CREATE TABLE IF NOT EXISTS spawned_wallets (
                    id INTEGER PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,
                    encrypted_key TEXT NOT NULL,
                    chain TEXT DEFAULT 'sui',
                    label TEXT,
                    created_at INTEGER NOT NULL
                );
        """)
        conn.close()
    else:
        conn = await get_connection()
        try:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS jwt_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    user_id TEXT,
                    token_hash TEXT NOT NULL,
                    expires_at INTEGER,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jwt_sessions_session_id ON jwt_sessions(session_id);

                CREATE TABLE IF NOT EXISTS server_wallet (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    chain TEXT DEFAULT 'sui',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(chain)
                );
                CREATE TABLE IF NOT EXISTS spawned_wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL UNIQUE,
                    encrypted_key TEXT NOT NULL,
                    chain TEXT DEFAULT 'sui',
                    label TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_spawned_wallets_chain ON spawned_wallets(chain);
            """)
            await conn.commit()
        finally:
            await conn.close()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def upsert_jwt_session(
    session_id: str,
    token: str,
    user_id: Optional[str] = None,
    expires_at: Optional[int] = None,
) -> None:
    """Store or update JWT session."""
    now = int(time.time())
    token_hash = _hash_token(token)
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        conn.execute(
            """INSERT INTO jwt_sessions (session_id, user_id, token_hash, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 user_id=excluded.user_id,
                 token_hash=excluded.token_hash,
                 expires_at=excluded.expires_at""",
            [session_id, user_id or "", token_hash, expires_at, now],
        )
        conn.close()
    else:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO jwt_sessions (session_id, user_id, token_hash, expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     user_id=excluded.user_id,
                     token_hash=excluded.token_hash,
                     expires_at=excluded.expires_at""",
                (session_id, user_id or "", token_hash, expires_at, now),
            )
            await conn.commit()
        finally:
            await conn.close()


async def get_server_wallet(chain: str = "sui") -> Optional[dict]:
    """Get server wallet for the given chain."""
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        row = conn.execute(
            "SELECT address, encrypted_key FROM server_wallet WHERE chain = ?",
            [chain],
        ).fetchone()
        conn.close()
        return {"address": row[0], "encrypted_key": row[1]} if row else None
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT address, encrypted_key FROM server_wallet WHERE chain = ?",
            (chain,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def upsert_spawned_wallet(address: str, encrypted_key: str, chain: str = "sui", label: Optional[str] = None) -> None:
    """Store a spawned wallet in spawned_wallets table."""
    now = int(time.time())
    label = label or ""
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        conn.execute(
            """INSERT INTO spawned_wallets (address, encrypted_key, chain, label, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(address) DO UPDATE SET
                 encrypted_key=excluded.encrypted_key,
                 label=excluded.label""",
            [address, encrypted_key, chain, label, now],
        )
        conn.close()
    else:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO spawned_wallets (address, encrypted_key, chain, label, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(address) DO UPDATE SET
                     encrypted_key=excluded.encrypted_key,
                     label=excluded.label""",
                (address, encrypted_key, chain, label, now),
            )
            await conn.commit()
        finally:
            await conn.close()


async def get_spawned_wallets(chain: str = "sui", limit: int = 10) -> list[dict]:
    """List spawned wallets for chain, newest first."""
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        rows = conn.execute(
            "SELECT address, label, created_at FROM spawned_wallets WHERE chain = ? ORDER BY created_at DESC LIMIT ?",
            [chain, limit],
        ).fetchall()
        conn.close()
        return [{"address": r[0], "label": r[1], "created_at": r[2]} for r in rows]
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT address, label, created_at FROM spawned_wallets WHERE chain = ? ORDER BY created_at DESC LIMIT ?",
            (chain, limit),
        )
        rows = await cursor.fetchall()
        return [{"address": row["address"], "label": row["label"] or "", "created_at": row["created_at"]} for row in rows]
    finally:
        await conn.close()


async def get_latest_spawned_wallet(chain: str = "sui") -> Optional[dict]:
    """Get the most recently spawned wallet for chain."""
    wallets = await get_spawned_wallets(chain=chain, limit=1)
    return wallets[0] if wallets else None


async def upsert_server_wallet(address: str, encrypted_key: str, chain: str = "sui") -> None:
    """Store or update server wallet."""
    now = int(time.time())
    if DB_BACKEND == "duckdb":
        import duckdb
        conn = duckdb.connect(DB_PATH)
        conn.execute(
            """INSERT INTO server_wallet (address, encrypted_key, chain, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(chain) DO UPDATE SET
                 address=excluded.address,
                 encrypted_key=excluded.encrypted_key,
                 updated_at=excluded.updated_at""",
            [address, encrypted_key, chain, now, now],
        )
        conn.close()
    else:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO server_wallet (address, encrypted_key, chain, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(chain) DO UPDATE SET
                     address=excluded.address,
                     encrypted_key=excluded.encrypted_key,
                     updated_at=excluded.updated_at""",
                (address, encrypted_key, chain, now, now),
            )
            await conn.commit()
        finally:
            await conn.close()
