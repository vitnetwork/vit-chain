"""
chain/core/chain.py — VITChain: block persistence using ChainBlock model.
No app.* or IoTEvent imports.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from chain.models import ChainBlock, ChainTransaction
from chain.core.block import VITBlock, validate_block
from chain.core.transaction import VITTransaction
from chain.core.state import ChainState

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64  # sentinel for first block


class VITChain:
    """Persistence wrapper — read/write blocks to PostgreSQL ChainBlock rows."""

    def __init__(self):
        self.state = ChainState()

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_height(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.max(ChainBlock.height)))
        h = result.scalar()
        return int(h) if h is not None else -1

    async def get_latest_block(self, db: AsyncSession) -> Optional[VITBlock]:
        result = await db.execute(
            select(ChainBlock).order_by(desc(ChainBlock.height)).limit(1)
        )
        row = result.scalar_one_or_none()
        return self._row_to_block(row) if row else None

    async def get_block_by_height(self, db: AsyncSession, height: int) -> Optional[VITBlock]:
        result = await db.execute(select(ChainBlock).where(ChainBlock.height == height))
        row = result.scalar_one_or_none()
        return self._row_to_block(row) if row else None

    async def get_block_by_hash(self, db: AsyncSession, block_hash: str) -> Optional[VITBlock]:
        result = await db.execute(select(ChainBlock).where(ChainBlock.block_hash == block_hash))
        row = result.scalar_one_or_none()
        return self._row_to_block(row) if row else None

    async def get_blocks(self, db: AsyncSession, limit: int = 20, offset: int = 0) -> list[VITBlock]:
        result = await db.execute(
            select(ChainBlock).order_by(desc(ChainBlock.height)).limit(limit).offset(offset)
        )
        return [self._row_to_block(r) for r in result.scalars().all()]

    async def get_transaction(self, db: AsyncSession, tx_hash: str) -> Optional[dict]:
        result = await db.execute(select(ChainTransaction).where(ChainTransaction.tx_hash == tx_hash))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "tx_hash": row.tx_hash,
            "block_height": row.block_height,
            "from_address": row.from_address,
            "to_address": row.to_address,
            "amount": str(row.amount),
            "nonce": row.nonce,
            "gas_fee": str(row.gas_fee),
            "tx_type": row.tx_type,
            "data": row.data,
            "timestamp": row.timestamp,
            "status": row.status,
        }

    async def chain_height(self, db: AsyncSession) -> int:
        return await self.get_height(db)

    # ── Write ─────────────────────────────────────────────────────────────────

    async def add_block(
        self,
        db: AsyncSession,
        block: VITBlock,
        known_validators: Optional[list[str]] = None,
        consensus_validator=None,
    ) -> bool:
        latest = await self.get_latest_block(db)

        if not validate_block(block, latest, known_validators, consensus_validator):
            logger.warning("[chain] Block %d failed validation.", block.height)
            return False

        # Apply transactions to state
        for tx in block.transactions:
            ok = await self.state.apply_transaction(db, tx, block_height=block.height)
            if not ok:
                logger.warning("[chain] Transaction %s failed in block %d.", tx.tx_hash, block.height)
                return False

        # Apply block reward to validator
        await self.state.apply_block_reward(db, block.validator_id, block.block_reward, block.height)

        # Persist block row
        raw_data = {
            "transactions": [tx.to_dict() for tx in block.transactions],
            "storage_proofs": block.storage_proofs,
            "consensus_votes": block.consensus_votes,
        }
        db_block = ChainBlock(
            height=block.height,
            block_hash=block.block_hash,
            prev_hash=block.prev_hash,
            merkle_root=block.merkle_root,
            timestamp=block.timestamp,
            validator_id=block.validator_id,
            validator_signature=block.validator_signature,
            tx_count=block.tx_count,
            total_fees=block.total_fees,
            block_reward=block.block_reward,
            storage_proofs=block.storage_proofs,
            consensus_votes=block.consensus_votes,
            raw_data=raw_data,
        )
        db.add(db_block)

        # Persist transaction rows
        for tx in block.transactions:
            db_tx = ChainTransaction(
                tx_hash=tx.tx_hash,
                block_height=block.height,
                from_address=tx.from_address,
                to_address=tx.to_address,
                amount=tx.amount,
                nonce=tx.nonce,
                gas_fee=tx.gas_fee,
                tx_type=tx.data.get("type", "transfer") if tx.data else "transfer",
                data=tx.data,
                signature=tx.signature,
                timestamp=tx.timestamp,
                status="confirmed",
            )
            db.add(db_tx)

        await db.flush()
        logger.info("[chain] Block %d added: %s…", block.height, block.block_hash[:16])
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _row_to_block(self, row: ChainBlock) -> VITBlock:
        raw = row.raw_data or {}
        txs = []
        for tx_data in raw.get("transactions", []):
            txs.append(VITTransaction(
                from_address=tx_data.get("from_address", ""),
                to_address=tx_data.get("to_address", ""),
                amount=Decimal(str(tx_data.get("amount", "0"))),
                nonce=tx_data.get("nonce", 0),
                timestamp=tx_data.get("timestamp", 0),
                gas_fee=Decimal(str(tx_data.get("gas_fee", "0"))),
                data=tx_data.get("data"),
                signature=tx_data.get("signature", ""),
                tx_hash=tx_data.get("tx_hash", ""),
                status=tx_data.get("status", "confirmed"),
            ))
        return VITBlock(
            height=row.height,
            prev_hash=row.prev_hash,
            merkle_root=row.merkle_root,
            timestamp=row.timestamp,
            validator_id=row.validator_id,
            transactions=txs,
            tx_count=row.tx_count or 0,
            total_fees=Decimal(str(row.total_fees or "0")),
            block_reward=Decimal(str(row.block_reward or "0")),
            validator_signature=row.validator_signature or "",
            block_hash=row.block_hash,
            storage_proofs=row.storage_proofs or [],
            consensus_votes=row.consensus_votes or [],
        )

    async def verify_chain_integrity(self, db: AsyncSession) -> bool:
        """Walk the chain and verify hash linkage."""
        height = await self.get_height(db)
        if height < 0:
            return True
        prev = None
        for h in range(0, min(height + 1, 100)):  # check up to first 100 blocks
            block = await self.get_block_by_height(db, h)
            if not block:
                return False
            if prev and block.prev_hash != prev.block_hash:
                return False
            prev = block
        return True
