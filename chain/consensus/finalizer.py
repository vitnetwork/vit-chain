"""
chain/consensus/finalizer.py — BlockFinalizer: marks checkpoint epochs as finalized.
"""
from __future__ import annotations
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from chain.models import ConsensusCheckpoint
from chain.config import settings

logger = logging.getLogger(__name__)


class BlockFinalizer:

    async def finalize(self, db: AsyncSession, epoch: int, block_hash: str, height: int) -> bool:
        result = await db.execute(
            select(ConsensusCheckpoint).where(ConsensusCheckpoint.epoch == epoch)
        )
        checkpoint = result.scalar_one_or_none()

        if checkpoint and checkpoint.finalized:
            return True

        if not checkpoint:
            checkpoint = ConsensusCheckpoint(
                epoch=epoch,
                block_hash=block_hash,
                height=height,
                finalized=True,
            )
            db.add(checkpoint)
        else:
            checkpoint.finalized = True

        await db.flush()
        logger.info("[finalizer] Epoch %d finalized at block %d.", epoch, height)
        return True

    async def is_finalized(self, db: AsyncSession, epoch: int) -> bool:
        result = await db.execute(
            select(ConsensusCheckpoint.finalized).where(ConsensusCheckpoint.epoch == epoch)
        )
        val = result.scalar_one_or_none()
        return bool(val)
