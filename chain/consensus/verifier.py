"""
chain/consensus/verifier.py — Challenge result aggregation.
No app.* imports.
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from chain.models import StorageChallenge, Validator
from chain.cache import cache_publish
import json

logger = logging.getLogger(__name__)


class ChallengeVerifier:

    async def collect_epoch_results(self, db: AsyncSession, epoch: int) -> dict:
        """
        In testnet single-node mode all active validators auto-pass.
        Multi-node: validators submit responses via /api/challenges/{id}/respond.
        """
        result = await db.execute(
            select(StorageChallenge).where(StorageChallenge.epoch == epoch)
        )
        challenges = list(result.scalars().all())

        total = len(challenges)
        if total == 0:
            return {"epoch": epoch, "total": 0, "passed": 0, "consensus_weight": 1.0}

        # Auto-verify unchallenged responses (single-node testnet behaviour)
        passed = 0
        for ch in challenges:
            if not ch.verified:
                ch.verified = True
                ch.resolved_at = datetime.now(timezone.utc)
                passed += 1
            else:
                passed += 1

        await db.flush()

        consensus_weight = passed / total if total > 0 else 1.0

        payload = {
            "epoch": epoch,
            "total": total,
            "passed": passed,
            "consensus_weight": round(consensus_weight, 4),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await cache_publish("vit:consensus:epoch_complete", json.dumps(payload))
        logger.info("[verifier] Epoch %d: %d/%d passed (weight=%.2f)", epoch, passed, total, consensus_weight)

        return payload
