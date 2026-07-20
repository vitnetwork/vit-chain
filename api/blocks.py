"""
api/blocks.py — Block query endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from chain.database import get_db
from chain.core.chain import VITChain

router = APIRouter(prefix="/api", tags=["Blocks"])
_chain = VITChain()


@router.get("/blocks")
async def list_blocks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    blocks = await _chain.get_blocks(db, limit=limit, offset=offset)
    height = await _chain.get_height(db)
    return {
        "total": height + 1 if height >= 0 else 0,
        "limit": limit,
        "offset": offset,
        "blocks": [b.to_dict() for b in blocks],
    }


@router.get("/blocks/latest")
async def latest_block(db: AsyncSession = Depends(get_db)):
    block = await _chain.get_latest_block(db)
    if not block:
        raise HTTPException(status_code=404, detail="No blocks yet")
    return block.to_dict()


@router.get("/blocks/{height}")
async def block_by_height(height: int, db: AsyncSession = Depends(get_db)):
    block = await _chain.get_block_by_height(db, height)
    if not block:
        raise HTTPException(status_code=404, detail=f"Block {height} not found")
    return block.to_dict()


@router.get("/blocks/hash/{block_hash}")
async def block_by_hash(block_hash: str, db: AsyncSession = Depends(get_db)):
    block = await _chain.get_block_by_hash(db, block_hash)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block.to_dict()
