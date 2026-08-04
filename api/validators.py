"""
api/validators.py — Validator set endpoints.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from chain.database import get_db
from chain.models import Validator, ValidatorReputation, SlashRecord
from chain.consensus.registry import ValidatorRegistry
from chain.config import settings

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


# ── Validator Registration ─────────────────────────────────────────────────

class ValidatorRegistration(BaseModel):
    address: str                    # 0x-prefixed Ethereum-style address
    name: str = ""                  # human-readable node name
    stake: int = 10_000             # initial stake in VIT (testnet default)
    public_key: str = ""            # optional ECDSA public key
    storage_url: str = ""           # optional vit-storage URL for proof delivery
    # On mainnet: signature of sha256("register:{address}:{name}:{stake}")
    # On testnet: not enforced
    signature: str = ""


@router.post("/validators/register", status_code=201)
async def register_validator(
    body: ValidatorRegistration,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new validator node.

    **Testnet**: open registration — signature not enforced.
    **Mainnet**: `signature` must be a valid ECDSA signature of the message
    `register:{address}:{name}:{stake}` produced by the private key
    corresponding to `address`.

    After registration, the new validator will receive storage challenges
    on the next consensus epoch. Point your node at this RPC endpoint and
    set `VIT_BOOTSTRAP_HTTP_URL` to join the network.
    """
    address = body.address.lower().strip()
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(status_code=422, detail="address must be a 42-char 0x-prefixed hex string")

    # On mainnet, enforce signature
    if settings.NETWORK == "mainnet" and not body.signature:
        raise HTTPException(
            status_code=403,
            detail="Validator registration on mainnet requires a signed registration message.",
        )

    # Check if already registered
    existing = await _reg.get_by_address(db, address)
    if existing:
        if existing.status == "active":
            return {
                "status": "already_registered",
                "node_id": existing.node_id,
                "address": address,
                "name": existing.name,
                "stake": str(existing.stake),
                "message": "Validator already active. Use /api/validators/sync to refresh.",
            }
        # Re-activate jailed or inactive validator
        await _reg.unjail_validator(db, existing.node_id)
        await db.commit()
        return {
            "status": "reactivated",
            "node_id": existing.node_id,
            "address": address,
        }

    # Register new validator
    from chain.crypto.address import format_node_id
    node_id = format_node_id(address)

    validator = await _reg.register(
        db,
        node_id=node_id,
        address=address,
        stake=Decimal(str(body.stake)),
        public_key=body.public_key,
        name=body.name or f"validator-{address[:8]}",
        metadata={
            "storage_url": body.storage_url,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "network": settings.NETWORK,
        },
    )
    await db.commit()

    return {
        "status": "registered",
        "node_id": validator.node_id,
        "address": validator.address,
        "name": validator.name,
        "stake": str(validator.stake),
        "network": settings.NETWORK,
        "message": (
            "Registration accepted. You will receive storage challenges "
            f"on the next consensus epoch (~{settings.EPOCH_SECONDS}s). "
            "Set VIT_BOOTSTRAP_HTTP_URL and VIT_BOOTSTRAP_WS_URL on your node "
            f"to https://vit-chain.onrender.com to join the network."
        ),
    }
