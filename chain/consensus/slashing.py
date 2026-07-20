"""
chain/consensus/slashing.py — SlashingManager.
No app.* imports.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from chain.models import Validator, SlashRecord
from chain.config import settings

logger = logging.getLogger(__name__)


class SlashReason(str, Enum):
    DOWNTIME      = "DOWNTIME"
    DOUBLE_SIGN   = "DOUBLE_SIGN"
    INVALID_BLOCK = "INVALID_BLOCK"


_SLASH_PCT = {
    SlashReason.DOWNTIME:      lambda: Decimal(str(settings.SLASH_DOWNTIME_PCT)) / 100,
    SlashReason.DOUBLE_SIGN:   lambda: Decimal(str(settings.SLASH_DOUBLE_SIGN_PCT)) / 100,
    SlashReason.INVALID_BLOCK: lambda: Decimal(str(settings.SLASH_INVALID_BLOCK_PCT)) / 100,
}


class SlashingManager:

    async def check_and_slash(
        self,
        db: AsyncSession,
        validator_address: str,
        reason: SlashReason,
        evidence: str = "",
        current_slot: int = 0,
    ) -> Optional[dict]:
        result = await db.execute(
            select(Validator).where(Validator.address == validator_address)
        )
        validator = result.scalar_one_or_none()
        if not validator or validator.status == "exited":
            return None

        stake_before = validator.stake
        pct = _SLASH_PCT[reason]()
        slash_amount = (stake_before * pct).quantize(Decimal("0.000001"))
        stake_after = max(Decimal("0"), stake_before - slash_amount)

        validator.stake = stake_after

        # Jail if stake drops to 0 or on double-sign
        if stake_after == Decimal("0") or reason == SlashReason.DOUBLE_SIGN:
            validator.status = "jailed"

        record = SlashRecord(
            validator_address=validator_address,
            reason=reason.value,
            slash_amount=slash_amount,
            stake_before=stake_before,
            stake_after=stake_after,
            evidence=evidence,
            slot=current_slot,
        )
        db.add(record)
        await db.flush()

        logger.warning(
            "[slashing] SLASH %s | reason=%s | -%s VIT | stake %s→%s",
            validator_address, reason.value, slash_amount, stake_before, stake_after,
        )

        return {
            "validator_address": validator_address,
            "reason": reason.value,
            "slash_amount": str(slash_amount),
            "stake_before": str(stake_before),
            "stake_after": str(stake_after),
        }


slashing_manager = SlashingManager()
