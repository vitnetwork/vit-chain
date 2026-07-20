"""
chain/genesis.py — Genesis block creation and idempotent seeding.
No app.* imports. No hardcoded private keys.
"""
from __future__ import annotations
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


def _require_treasury_key() -> str:
    key = settings.GENESIS_TREASURY_KEY.strip()
    if not key:
        raise RuntimeError(
            "GENESIS_TREASURY_KEY is not set. "
            "Generate a wallet and set this secret in Render — never commit it."
        )
    return key


def _require_validator_key() -> str:
    """Return validator key for block signing (falls back to treasury key in dev)."""
    key = settings.VIT_VALIDATOR_KEY.strip()
    if not key:
        key = settings.GENESIS_TREASURY_KEY.strip()
    if not key:
        raise RuntimeError(
            "VIT_VALIDATOR_KEY (or GENESIS_TREASURY_KEY) must be set to start the chain."
        )
    return key


def build_genesis_block() -> VITBlock:
    """Build block at height=0 — mints INITIAL_SUPPLY_VIT to the treasury address."""
    treasury_key = _require_treasury_key()
    validator_key = _require_validator_key()

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
    """
    chain = VITChain()
    existing = await chain.get_block_by_height(db, 0)
    if existing:
        logger.info("[genesis] Genesis already exists at height 0: %s…", existing.block_hash[:16])
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


async def _register_genesis_validators(db: AsyncSession) -> None:
    """Register GENESIS_VALIDATORS from env into the validator registry."""
    from chain.consensus.registry import ValidatorRegistry

    registry = ValidatorRegistry()
    validators = settings.genesis_validators()

    if not validators:
        # Auto-register the local node if VIT_VALIDATOR_KEY is set
        validator_key = settings.VIT_VALIDATOR_KEY.strip() or settings.GENESIS_TREASURY_KEY.strip()
        if validator_key:
            address = private_key_to_address(validator_key)
            node_id = format_node_id(address)
            await registry.register(db, node_id=node_id, address=address,
                                     stake=Decimal("1000000"), name="genesis-validator")
            logger.info("[genesis] Auto-registered local validator: %s", address)
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
        logger.info("[genesis] Registered genesis validator: %s (stake=%s)", v["address"], v["stake"])
