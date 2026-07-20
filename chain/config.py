"""
chain/config.py — Self-contained configuration for the VIT Chain node.
All values come from environment variables only (no app.* imports).
"""
import os
import logging

logger = logging.getLogger(__name__)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _int_env(key: str, default: int = 0) -> int:
    return int(os.getenv(key, str(default)))


class _Settings:
    # ── Identity ────────────────────────────────────────────────────────────
    NODE_VERSION: str = "1.0.0"
    NETWORK: str = _env("NETWORK", "testnet")          # testnet | mainnet
    CHAIN_ID: int = _int_env("CHAIN_ID", 7764)
    NODE_NAME: str = _env("VIT_NODE_NAME", "vit-chain-node-1")
    LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")

    # ── Chain constants ──────────────────────────────────────────────────────
    EPOCH_SECONDS: int = _int_env("EPOCH_SECONDS", 15)
    CHECKPOINT_INTERVAL: int = _int_env("CHECKPOINT_INTERVAL", 100)
    INITIAL_SUPPLY_VIT: int = _int_env("INITIAL_SUPPLY_VIT", 1_000_000)
    BLOCK_REWARD_VIT: float = float(_env("BLOCK_REWARD_VIT", "10.0"))
    GAS_PRICE_WEI: int = 1_000_000_000  # 1 gwei equivalent

    # ── Genesis ──────────────────────────────────────────────────────────────
    # GENESIS_TREASURY_KEY: private key hex (32 bytes) for treasury wallet.
    # Never hardcode — must be set via Render secret.
    GENESIS_TREASURY_KEY: str = _env("GENESIS_TREASURY_KEY", "")
    GENESIS_PROPOSER_ADDRESS: str = _env("GENESIS_PROPOSER_ADDRESS", "")
    # Comma-separated: address:stake_vit:name  e.g. "0xABC:1000000:node1"
    GENESIS_VALIDATORS_RAW: str = _env("GENESIS_VALIDATORS", "")
    GENESIS_TIMESTAMP: int = 1735689600  # 2025-01-01 00:00:00 UTC (canonical)

    # ── Validator / Consensus ────────────────────────────────────────────────
    VIT_VALIDATOR_KEY: str = _env("VIT_VALIDATOR_KEY", "")
    VIT_NODE_ID: str = _env("VIT_NODE_ID", "")

    # ── Slashing ─────────────────────────────────────────────────────────────
    SLASHING_DOWNTIME_SLOTS: int = _int_env("SLASHING_DOWNTIME_SLOTS", 50)
    SLASHING_APPEAL_WINDOW_SLOTS: int = _int_env("SLASHING_APPEAL_WINDOW_SLOTS", 100)
    SLASH_DOWNTIME_PCT: float = float(_env("SLASH_DOWNTIME_PCT", "5.0"))
    SLASH_DOUBLE_SIGN_PCT: float = float(_env("SLASH_DOUBLE_SIGN_PCT", "20.0"))
    SLASH_INVALID_BLOCK_PCT: float = float(_env("SLASH_INVALID_BLOCK_PCT", "10.0"))

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = _env("DATABASE_URL", "sqlite+aiosqlite:///./vitchain.db")
    DB_POOL_SIZE: int = _int_env("DB_POOL_SIZE", 10)
    DB_MAX_OVERFLOW: int = _int_env("DB_MAX_OVERFLOW", 20)

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = _env("REDIS_URL", "")

    # ── P2P ───────────────────────────────────────────────────────────────────
    VIT_BOOTSTRAP_WS_URL: str = _env("VIT_BOOTSTRAP_WS_URL", "")
    VIT_BOOTSTRAP_HTTP_URL: str = _env("VIT_BOOTSTRAP_HTTP_URL", "")
    P2P_MAX_PEERS: int = _int_env("P2P_MAX_PEERS", 50)
    P2P_ENABLED: bool = _env("P2P_ENABLED", "true").lower() == "true"

    # ── Cross-service URLs ────────────────────────────────────────────────────
    VIT_STORAGE_URL: str = _env("VIT_STORAGE_URL", "")
    VIT_AI_URL: str = _env("VIT_AI_URL", "")

    def genesis_validators(self) -> list[dict]:
        """Parse GENESIS_VALIDATORS env into list of {address, stake, name}."""
        raw = self.GENESIS_VALIDATORS_RAW.strip()
        if not raw:
            logger.warning(
                "[config] GENESIS_VALIDATORS not set — "
                "chain starts with no bootstrap validators (dev only)."
            )
            return []
        result = []
        for entry in raw.split(","):
            parts = entry.strip().split(":")
            if len(parts) < 2:
                logger.warning("[config] Skipping malformed GENESIS_VALIDATORS entry: %r", entry)
                continue
            address, stake_str = parts[0].strip(), parts[1].strip()
            name = parts[2].strip() if len(parts) > 2 else ""
            try:
                result.append({"address": address, "stake": int(stake_str), "name": name})
            except ValueError:
                logger.warning("[config] Invalid stake in GENESIS_VALIDATORS: %r", entry)
        return result


settings = _Settings()
