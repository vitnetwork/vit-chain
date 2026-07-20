"""
api/accounts.py — Account balance and history endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from chain.database import get_db
from chain.models import ChainAccount, ChainTransaction

router = APIRouter(prefix="/api", tags=["Accounts"])


@router.get("/accounts/{address}")
async def get_account(address: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChainAccount).where(ChainAccount.address == address))
    account = result.scalar_one_or_none()
    if not account:
        # Return zero-balance account (EVM behaviour)
        return {
            "address": address,
            "balance": "0",
            "staked": "0",
            "nonce": 0,
            "first_seen_height": None,
            "last_active_height": None,
        }
    return {
        "address": account.address,
        "balance": str(account.balance),
        "staked": str(account.staked),
        "nonce": account.nonce,
        "first_seen_height": account.first_seen_height,
        "last_active_height": account.last_active_height,
    }


@router.get("/accounts/{address}/transactions")
async def get_account_txs(address: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChainTransaction)
        .where(or_(ChainTransaction.from_address == address, ChainTransaction.to_address == address))
        .order_by(desc(ChainTransaction.timestamp))
        .limit(limit)
    )
    rows = result.scalars().all()
    return {
        "address": address,
        "transactions": [
            {
                "tx_hash": r.tx_hash,
                "block_height": r.block_height,
                "from_address": r.from_address,
                "to_address": r.to_address,
                "amount": str(r.amount),
                "gas_fee": str(r.gas_fee),
                "tx_type": r.tx_type,
                "timestamp": r.timestamp,
                "status": r.status,
            }
            for r in rows
        ],
    }
