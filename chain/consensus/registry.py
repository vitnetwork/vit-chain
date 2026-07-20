"""
chain/consensus/registry.py — ValidatorRegistry.
No app.* imports.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from chain.models import Validator, ValidatorReputation

logger = logging.getLogger(__name__)


class ValidatorRegistry:

    async def register(
        self,
        db: AsyncSession,
        node_id: str,
        address: str,
        stake: Decimal = Decimal("0"),
        public_key: str = "",
        name: str = "",
        metadata: Optional[dict] = None,
    ) -> Validator:
        result = await db.execute(select(Validator).where(Validator.node_id == node_id))
        validator = result.scalar_one_or_none()

        if validator:
            validator.public_key = public_key or validator.public_key
            validator.last_active = datetime.now(timezone.utc)
            if metadata:
                validator.extra_metadata = metadata
        else:
            validator = Validator(
                node_id=node_id,
                address=address,
                public_key=public_key,
                stake=stake,
                status="active",
                name=name,
                extra_metadata=metadata or {},
            )
            db.add(validator)
            await db.flush()

            reputation = ValidatorReputation(node_id=node_id)
            db.add(reputation)

        await db.flush()
        return validator

    async def get_active_validators(self, db: AsyncSession) -> list[Validator]:
        result = await db.execute(select(Validator).where(Validator.status == "active"))
        return list(result.scalars().all())

    async def get_validator(self, db: AsyncSession, node_id: str) -> Optional[Validator]:
        result = await db.execute(select(Validator).where(Validator.node_id == node_id))
        return result.scalar_one_or_none()

    async def get_by_address(self, db: AsyncSession, address: str) -> Optional[Validator]:
        result = await db.execute(select(Validator).where(Validator.address == address))
        return result.scalar_one_or_none()

    async def jail_validator(self, db: AsyncSession, node_id: str, reason: str = "") -> None:
        await db.execute(
            update(Validator)
            .where(Validator.node_id == node_id)
            .values(status="jailed")
        )
        logger.warning("[registry] Validator jailed: %s reason=%s", node_id, reason)

    async def unjail_validator(self, db: AsyncSession, node_id: str) -> None:
        await db.execute(
            update(Validator).where(Validator.node_id == node_id).values(status="active")
        )

    async def is_active(self, db: AsyncSession, node_id: str) -> bool:
        result = await db.execute(
            select(Validator.status).where(Validator.node_id == node_id)
        )
        status = result.scalar_one_or_none()
        return status == "active"

    async def update_stake(self, db: AsyncSession, node_id: str, new_stake: Decimal) -> None:
        await db.execute(
            update(Validator).where(Validator.node_id == node_id).values(stake=new_stake)
        )

    async def record_block_produced(self, db: AsyncSession, node_id: str) -> None:
        result = await db.execute(
            select(ValidatorReputation).where(ValidatorReputation.node_id == node_id)
        )
        rep = result.scalar_one_or_none()
        if rep:
            rep.blocks_produced += 1
            rep.miss_streak = 0

    async def record_block_missed(self, db: AsyncSession, node_id: str) -> int:
        """Returns updated miss_streak."""
        result = await db.execute(
            select(ValidatorReputation).where(ValidatorReputation.node_id == node_id)
        )
        rep = result.scalar_one_or_none()
        if rep:
            rep.blocks_missed += 1
            rep.miss_streak += 1
            return rep.miss_streak
        return 0
