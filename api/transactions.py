"""
api/transactions.py — Transaction query and submission endpoints.
"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Body, Query
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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChainTransaction)
        .order_by(desc(ChainTransaction.timestamp))
        .offset(offset)
        .limit(limit)
    )
    total = await db.scalar(select(func.count(ChainTransaction.tx_hash))) or 0
    transactions = [
        {
            "tx_hash": tx.tx_hash,
            "block_height": tx.block_height,
            "from_address": tx.from_address,
            "to_address": tx.to_address,
            "amount": str(tx.amount),
            "nonce": tx.nonce,
            "gas_fee": str(tx.gas_fee),
            "tx_type": tx.tx_type,
            "data": tx.data,
            "timestamp": tx.timestamp,
            "status": tx.status,
        }
        for tx in result.scalars().all()
    ]
    return {"transactions": transactions, "total": total, "limit": limit, "offset": offset}


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
