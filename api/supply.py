"""
api/supply.py — Supply accounting contract for the standalone VIT Chain node.
"""
import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chain.database import get_db
from chain.models import ChainAccount

router = APIRouter(prefix="/api", tags=["Supply"])


@router.get("/supply")
async def get_supply(db: AsyncSession = Depends(get_db)):
    """Canonical supply snapshot used by the platform and external clients."""
    total_supply = await db.scalar(select(func.coalesce(func.sum(ChainAccount.balance), 0))) or 0
    staked_supply = await db.scalar(select(func.coalesce(func.sum(ChainAccount.staked), 0))) or 0
    total_accounts = await db.scalar(select(func.count(ChainAccount.address))) or 0

    return {
        "max_supply": "1000000000",
        "total_supply": str(total_supply),
        "circulating_supply": str(total_supply),
        "staked_supply": str(staked_supply),
        "locked_supply": "0",
        "treasury_supply": "0",
        "burned_supply": "0",
        "issued_supply": str(total_supply),
        "total_accounts": total_accounts,
        "updated_at": int(time.time()),
    }
