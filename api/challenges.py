"""
api/challenges.py — Storage challenge response endpoints.
Allows external storage validators (e.g. vit-storage) to respond to open
challenges and submit on-chain storage proofs.
"""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from chain.database import get_db
from chain.models import StorageChallenge, Validator, ChainBlock

router = APIRouter(prefix="/api", tags=["Challenges"])


class ProofResponse(BaseModel):
    validator_address: str
    proof_hash: str          # SHA-256 of proved shard data
    shard_id: str | None = None
    signature: str | None = None  # ECDSA sig — required on mainnet, optional testnet
    metadata: dict | None = None


@router.get("/challenges/pending")
async def pending_challenges(
    validator: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Return open (unverified) storage challenges for a given validator address.
    vit-storage calls this endpoint each epoch to discover what to prove.
    """
    result = await db.execute(
        select(StorageChallenge)
        .where(StorageChallenge.validator_address == validator)
        .where(StorageChallenge.verified == False)  # noqa: E712
        .order_by(StorageChallenge.epoch.desc())
        .limit(limit)
    )
    challenges = list(result.scalars().all())
    return {
        "validator": validator,
        "pending": len(challenges),
        "challenges": [
            {
                "challenge_id": c.challenge_id,
                "epoch": c.epoch,
                "challenge_data": c.challenge_data,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in challenges
        ],
    }


@router.post("/challenges/{challenge_id}/respond")
async def respond_to_challenge(
    challenge_id: str,
    body: ProofResponse,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a storage proof response for an open challenge.
    Marks the challenge as verified and patches the latest block's
    storage_proofs array with the submitted proof — making PoS evidence
    visible on-chain.
    """
    result = await db.execute(
        select(StorageChallenge).where(StorageChallenge.challenge_id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if challenge.verified:
        return {"status": "already_verified", "challenge_id": challenge_id}
    if challenge.validator_address.lower() != body.validator_address.lower():
        raise HTTPException(status_code=403, detail="Validator address mismatch")

    # Mark challenge verified
    now = datetime.now(timezone.utc)
    challenge.verified = True
    challenge.resolved_at = now
    if isinstance(challenge.challenge_data, dict):
        challenge.challenge_data = {
            **challenge.challenge_data,
            "proof_hash": body.proof_hash,
            "shard_id": body.shard_id,
            "responded_at": now.isoformat(),
            "metadata": body.metadata or {},
        }

    # Append proof to the latest block's storage_proofs JSON column
    # This makes the proof visible in the block explorer immediately.
    try:
        block_result = await db.execute(
            select(ChainBlock).order_by(ChainBlock.height.desc()).limit(1)
        )
        latest_block = block_result.scalar_one_or_none()
        if latest_block is not None:
            existing = list(latest_block.storage_proofs or [])
            existing.append({
                "challenge_id": challenge_id,
                "epoch": challenge.epoch,
                "validator": body.validator_address,
                "proof_hash": body.proof_hash,
                "shard_id": body.shard_id,
                "timestamp": now.isoformat(),
            })
            # SQLAlchemy JSON mutation must use assignment to trigger dirty tracking
            latest_block.storage_proofs = existing
    except Exception:
        pass  # Block proof patching is best-effort; don't fail the response

    await db.commit()
    return {
        "status": "accepted",
        "challenge_id": challenge_id,
        "epoch": challenge.epoch,
        "validator": body.validator_address,
        "proof_hash": body.proof_hash,
    }


@router.get("/challenges/stats")
async def challenge_stats(db: AsyncSession = Depends(get_db)):
    """Summary stats for the challenge system."""
    from sqlalchemy import func
    total_r = await db.execute(select(func.count(StorageChallenge.challenge_id)))
    verified_r = await db.execute(
        select(func.count(StorageChallenge.challenge_id))
        .where(StorageChallenge.verified == True)  # noqa: E712
    )
    pending_r = await db.execute(
        select(func.count(StorageChallenge.challenge_id))
        .where(StorageChallenge.verified == False)  # noqa: E712
    )
    latest_epoch_r = await db.execute(
        select(func.max(StorageChallenge.epoch))
    )
    return {
        "total": total_r.scalar() or 0,
        "verified": verified_r.scalar() or 0,
        "pending": pending_r.scalar() or 0,
        "latest_epoch": latest_epoch_r.scalar() or 0,
    }
