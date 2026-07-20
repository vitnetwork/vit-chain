"""
chain/consensus/reputation.py — Validator reputation tracking.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from chain.models import ValidatorReputation, Validator

logger = logging.getLogger(__name__)


class ReputationManager:

    async def record_produced(self, db: AsyncSession, node_id: str) -> None:
        result = await db.execute(
            select(ValidatorReputation).where(ValidatorReputation.node_id == node_id)
        )
        rep = result.scalar_one_or_none()
        if rep:
            rep.blocks_produced += 1
            rep.miss_streak = 0
            rep.score = min(Decimal("1.0"), rep.score + Decimal("0.001"))

    async def record_missed(self, db: AsyncSession, node_id: str) -> int:
        result = await db.execute(
            select(ValidatorReputation).where(ValidatorReputation.node_id == node_id)
        )
        rep = result.scalar_one_or_none()
        if not rep:
            return 0
        rep.blocks_missed += 1
        rep.miss_streak += 1
        rep.score = max(Decimal("0.0"), rep.score - Decimal("0.005"))
        return rep.miss_streak

    async def get_score(self, db: AsyncSession, node_id: str) -> float:
        result = await db.execute(
            select(ValidatorReputation.score).where(ValidatorReputation.node_id == node_id)
        )
        score = result.scalar_one_or_none()
        return float(score) if score else 1.0
