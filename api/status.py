"""
api/status.py — GET /status — full chain node status.
"""
import time
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from chain.database import get_db
from chain.config import settings
from chain.core.chain import VITChain
from chain.consensus.registry import ValidatorRegistry
from chain.p2p.gossip import peer_count

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
