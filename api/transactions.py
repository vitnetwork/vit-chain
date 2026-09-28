"""
api/transactions.py — Transaction query and submission endpoints.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, select
from pydantic import BaseModel
from chain.database import get_db
from chain.core.chain import VITChain
from chain.core.transaction import VITTransaction
from chain.consensus.producer import mempool
from chain.models import ChainTransaction

router = APIRouter(prefix="/api", tags=["Transactions"])
_chain = VITChain()


class SendTxRequest(BaseModel):
    from_address: str
    to_address: str
    amount: str
    nonce: int
    gas_fee: str = "0"
    signature: str
    tx_hash: str
    data: dict | None = None


@router.get("/txs")
async def list_transactions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Return recent persisted transactions without exposing signatures."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be non-negative")

    total_result = await db.execute(select(func.count()).select_from(ChainTransaction))
    total = int(total_result.scalar_one() or 0)
    result = await db.execute(
        select(ChainTransaction)
        .order_by(desc(ChainTransaction.timestamp), desc(ChainTransaction.tx_hash))
        .offset(offset)
        .limit(limit)
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "transactions": [
            {
                "tx_hash": row.tx_hash,
                "block_height": row.block_height,
                "from_address": row.from_address,
                "to_address": row.to_address,
                "amount": str(row.amount),
                "gas_fee": str(row.gas_fee),
                "tx_type": row.tx_type,
                "data": row.data,
                "timestamp": row.timestamp,
                "status": row.status,
            }
            for row in result.scalars().all()
        ],
    }


@router.get("/txs/{tx_hash}")
async def get_transaction(tx_hash: str, db: AsyncSession = Depends(get_db)):
    tx = await _chain.get_transaction(db, tx_hash)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.post("/txs")
async def submit_transaction(body: SendTxRequest):
    """Submit a signed transaction to the mempool."""
    import time
    tx = VITTransaction(
        from_address=body.from_address,
        to_address=body.to_address,
        amount=Decimal(body.amount),
        nonce=body.nonce,
        timestamp=int(time.time()),
        gas_fee=Decimal(body.gas_fee),
        data=body.data,
        signature=body.signature,
        tx_hash=body.tx_hash,
        status="pending",
    )
    ok = mempool.add(tx)
    if not ok:
        raise HTTPException(status_code=400, detail="Transaction rejected (invalid, duplicate, or mempool full)")
    return {"status": "accepted", "tx_hash": tx.tx_hash, "pool_size": mempool.size()}


@router.get("/mempool")
async def get_mempool():
    pending = mempool.get_pending(limit=100)
    return {
        "size": mempool.size(),
        "transactions": [tx.to_dict() for tx in pending],
    }
