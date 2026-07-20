"""
chain/consensus/challenge.py — Storage challenge generation for PoS epochs.
No app.* imports.
"""
from __future__ import annotations
import logging
import time
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from chain.models import StorageChallenge, Validator
from chain.crypto.hash import sha256_hex

logger = logging.getLogger(__name__)

CHALLENGE_WINDOW_SECONDS = 10


class ChallengeGenerator:

    async def generate_epoch_challenges(self, db: AsyncSession, epoch: int) -> list[str]:
        """Generate one storage challenge per active validator for this epoch."""
        result = await db.execute(select(Validator).where(Validator.status == "active"))
        validators = list(result.scalars().all())

        if not validators:
            logger.debug("[challenge] No active validators for epoch %d.", epoch)
            return []

        challenge_ids = []
        for v in validators:
            challenge_id = sha256_hex(f"epoch:{epoch}:validator:{v.address}:{time.time()}".encode())
            challenge_data = {
                "epoch": epoch,
                "validator": v.address,
                "nonce": str(uuid.uuid4()),
                "target": "random_shard",
            }
            ch = StorageChallenge(
                challenge_id=challenge_id,
                epoch=epoch,
                validator_address=v.address,
                shard_id=None,
                challenge_data=challenge_data,
                verified=False,
            )
            db.add(ch)
            challenge_ids.append(challenge_id)

        await db.flush()
        logger.debug("[challenge] Generated %d challenges for epoch %d.", len(challenge_ids), epoch)
        return challenge_ids
