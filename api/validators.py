"""
api/validators.py — Validator set endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from chain.database import get_db
from chain.models import Validator, ValidatorReputation, SlashRecord
from chain.consensus.registry import ValidatorRegistry

router = APIRouter(prefix="/api", tags=["Validators"])
_reg = ValidatorRegistry()


@router.get("/validators")
async def list_validators(db: AsyncSession = Depends(get_db)):
    validators = await _reg.get_active_validators(db)
    return {
        "count": len(validators),
        "validators": [
            {
                "node_id": v.node_id,
                "address": v.address,
                "name": v.name,
                "stake": str(v.stake),
                "status": v.status,
            }
            for v in validators
        ],
    }


@router.get("/validators/{address}")
async def get_validator(address: str, db: AsyncSession = Depends(get_db)):
    v = await _reg.get_by_address(db, address)
    if not v:
        raise HTTPException(status_code=404, detail="Validator not found")

    result = await db.execute(
        select(ValidatorReputation).where(ValidatorReputation.node_id == v.node_id)
    )
    rep = result.scalar_one_or_none()

    slash_result = await db.execute(
        select(SlashRecord).where(SlashRecord.validator_address == address)
    )
    slashes = slash_result.scalars().all()

    return {
        "node_id": v.node_id,
        "address": v.address,
        "name": v.name,
        "stake": str(v.stake),
        "status": v.status,
        "reputation": {
            "blocks_produced": rep.blocks_produced if rep else 0,
            "blocks_missed": rep.blocks_missed if rep else 0,
            "miss_streak": rep.miss_streak if rep else 0,
            "score": str(rep.score) if rep else "1.0",
        } if rep else None,
        "slashes": [
            {
                "reason": s.reason,
                "slash_amount": str(s.slash_amount),
                "stake_before": str(s.stake_before),
                "stake_after": str(s.stake_after),
                "slot": s.slot,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in slashes
        ],
    }
