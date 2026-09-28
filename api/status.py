"""
api/status.py — GET /status — full chain node status.
"""
import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, select
from chain.database import get_db
from chain.config import settings
from chain.core.chain import VITChain
from chain.consensus.registry import ValidatorRegistry
from chain.p2p.gossip import peer_count
from chain.models import ChainBlock, ChainTransaction, Validator

router = APIRouter(prefix="/api", tags=["Status"])
_chain = VITChain()
_reg = ValidatorRegistry()


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    height = await _chain.get_height(db)
    latest = await _chain.get_latest_block(db)
    validators = await _reg.get_active_validators(db)

    return {
        "network":          settings.NETWORK,
        "chain_id":         settings.CHAIN_ID,
        "node_version":     settings.NODE_VERSION,
        "block_height":     height,
        "latest_block_hash": latest.block_hash if latest else None,
        "latest_block_ts":  latest.timestamp if latest else None,
        "epoch_seconds":    settings.EPOCH_SECONDS,
        "active_validators": len(validators),
        "connected_peers":  peer_count(),
        "server_time":      int(time.time()),
    }


@router.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)):
    """Return explorer metrics derived from persisted chain data."""
    height = await _chain.get_height(db)
    total_result = await db.execute(select(func.count()).select_from(ChainTransaction))
    recent_result = await db.execute(
        select(func.count()).select_from(ChainTransaction).where(
            ChainTransaction.timestamp >= int(time.time()) - 60
        )
    )
    validators_result = await db.execute(
        select(func.count()).select_from(Validator).where(Validator.status == "active")
    )
    timestamps_result = await db.execute(
        select(ChainBlock.timestamp).order_by(desc(ChainBlock.height)).limit(2)
    )
    timestamps = list(timestamps_result.scalars().all())
    avg_block_time = (
        max(0, timestamps[0] - timestamps[1]) if len(timestamps) == 2 else None
    )

    return {
        "height": height,
        "tps": round(int(recent_result.scalar_one() or 0) / 60, 4),
        "total_transactions": int(total_result.scalar_one() or 0),
        "active_validators": int(validators_result.scalar_one() or 0),
        "avg_block_time": avg_block_time,
    }
