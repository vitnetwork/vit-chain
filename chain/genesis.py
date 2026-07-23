"""
chain/genesis.py — Genesis block creation and idempotent seeding.
No app.* imports. No hardcoded private keys.
"""
from __future__ import annotations
import hashlib
import logging
import time
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from chain.config import settings
from chain.core.block import VITBlock, build_block
from chain.core.transaction import VITTransaction
from chain.core.chain import VITChain
from chain.crypto.address import private_key_to_address, format_node_id, ZERO_ADDRESS
from chain.crypto.hash import keccak256_hex

logger = logging.getLogger(__name__)


def _auto_treasury_key() -> str:
    """
    Return a deterministic 32-byte hex key derived from public chain constants.
    ONLY used on testnet when GENESIS_TREASURY_KEY is unset.
    On mainnet, raises ValueError.
    """
    if settings.NETWORK == "mainnet":
        raise ValueError(
            "GENESIS_TREASURY_KEY must be set via environment variable on mainnet. "
            "Never use auto-generated keys in production."
        )
    key = hashlib.sha256(
        f"vit-{settings.NETWORK}-genesis-treasury-{settings.CHAIN_ID}".encode()
    ).hexdigest()
    logger.warning(
        "[genesis] GENESIS_TREASURY_KEY not set — using auto-generated deterministic key "
        "(testnet only). Set this env var for a stable identity."
    )
    return key


def _auto_validator_key() -> str:
    """
    Return a deterministic 32-byte hex validator key derived from public chain constants.
    ONLY used on testnet when VIT_VALIDATOR_KEY is unset.
    On mainnet, raises ValueError.
    """
    if settings.NETWORK == "mainnet":
        raise ValueError(
            "VIT_VALIDATOR_KEY must be set via environment variable on mainnet. "
            "Never use auto-generated keys in production."
        )
    key = hashlib.sha256(
        f"vit-{settings.NETWORK}-validator-1-{settings.CHAIN_ID}".encode()
    ).hexdigest()
    logger.warning(
        "[genesis] VIT_VALIDATOR_KEY not set — using auto-generated deterministic key "
        "(testnet only). Set this env var for a stable validator identity."
    )
    return key


def _resolve_treasury_key() -> str:
    """Return effective treasury key — from env or auto-generated for testnet."""
    key = settings.GENESIS_TREASURY_KEY.strip()
    if not key:
        key = _auto_treasury_key()
    return key


def _resolve_validator_key() -> str:
    """Return effective validator key — from env, falls back to treasury, then auto-generates."""
    key = settings.VIT_VALIDATOR_KEY.strip()
    if not key:
        key = settings.GENESIS_TREASURY_KEY.strip()
    if not key:
        key = _auto_validator_key()
    return key


def build_genesis_block() -> VITBlock:
    """Build block at height=0 — mints INITIAL_SUPPLY_VIT to the treasury address."""
    treasury_key = _resolve_treasury_key()
    validator_key = _resolve_validator_key()

    treasury_address = private_key_to_address(treasury_key)
    validator_address = private_key_to_address(validator_key)

    logger.info("[genesis] Treasury address: %s", treasury_address)
    logger.info("[genesis] Validator address: %s", validator_address)

    # Genesis mint transaction — from zero address to treasury
    tx_hash = keccak256_hex(
        f"genesis:mint:{treasury_address}:{settings.INITIAL_SUPPLY_VIT}:{settings.GENESIS_TIMESTAMP}".encode()
    )
    genesis_tx = VITTransaction(
        from_address=ZERO_ADDRESS,
        to_address=treasury_address,
        amount=Decimal(str(settings.INITIAL_SUPPLY_VIT)),
        nonce=0,
        timestamp=settings.GENESIS_TIMESTAMP,
        gas_fee=Decimal("0"),
        data={"type": "genesis_mint", "network": settings.NETWORK},
        signature="",
        tx_hash=tx_hash,
        status="confirmed",
    )

    block = build_block(
        prev_block=None,
        transactions=[genesis_tx],
        storage_proofs=[],
        validator_key=validator_key,
        height=0,
        timestamp=settings.GENESIS_TIMESTAMP,
    )

    logger.info("[genesis] Genesis block built: hash=%s…", block.block_hash[:16])
    return block


async def ensure_genesis(db: AsyncSession) -> VITBlock:
    """
    Idempotent — returns existing genesis block if already seeded,
    otherwise builds and persists it.

    Also ensures validators are registered even if genesis was previously
    seeded without them (e.g. after a revert or schema migration).
    """
    chain = VITChain()
    existing = await chain.get_block_by_height(db, 0)
    if existing:
        logger.info(
            "[genesis] Genesis already exists at height 0: %s…", existing.block_hash[:16]
        )
        # Guard: ensure validators are registered even when genesis pre-exists.
        # This handles cases where genesis was seeded before validator registration
        # was introduced, or after a database reset without a full redeploy.
        await _ensure_validators_registered(db)
        return existing

    logger.info("[genesis] No genesis block found — seeding now.")
    genesis_block = build_genesis_block()

    ok = await chain.add_block(db, genesis_block, known_validators=None)
    if not ok:
        raise RuntimeError("Genesis block failed chain.add_block() — check logs.")

    # Register genesis validators from env
    await _register_genesis_validators(db)

    logger.info("[genesis] Genesis seeded successfully.")
    return genesis_block


async def _ensure_validators_registered(db: AsyncSession) -> None:
    """
    Check if any active validators exist; register them if not.
    Called on every boot so a node that lost its validator state recovers
    automatically — without recreating the genesis block.
    """
    import traceback
    from chain.consensus.registry import ValidatorRegistry

    registry = ValidatorRegistry()
    active = await registry.get_active_validators(db)
    if active:
        logger.info(
            "[genesis] %d active validator(s) already registered — skipping re-registration.",
            len(active),
        )
        return

    logger.warning(
        "[genesis] Genesis exists but no active validators found — "
        "re-registering from env / auto-generated keys."
    )
    try:
        await _register_genesis_validators(db)
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("[genesis] Validator registration FAILED: %s\n%s", exc, tb)
        # Store error so it's visible via /api/startup-errors
        from chain.startup_log import capture as _cap
        _cap("validator_registration", exc)
        raise


async def _register_genesis_validators(db: AsyncSession) -> None:
    """Register GENESIS_VALIDATORS from env into the validator registry."""
    from chain.consensus.registry import ValidatorRegistry

    registry = ValidatorRegistry()
    validators = settings.genesis_validators()

    if not validators:
        # No validators configured — auto-register using the resolved validator key.
        # This ensures block production can start immediately on testnet.
        validator_key = _resolve_validator_key()
        address = private_key_to_address(validator_key)
        node_id = format_node_id(address)
        await registry.register(
            db,
            node_id=node_id,
            address=address,
            stake=Decimal("1000000"),
            name="genesis-validator-1",
        )
        logger.info("[genesis] Auto-registered default genesis validator: %s", address)
        return

    for v in validators:
        node_id = format_node_id(v["address"])
        await registry.register(
            db,
            node_id=node_id,
            address=v["address"],
            stake=Decimal(str(v["stake"])),
            name=v.get("name", ""),
        )
        logger.info(
            "[genesis] Registered genesis validator: %s (stake=%s)",
            v["address"],
            v["stake"],
        )
