"""
chain/consensus/engine.py — ConsensusManager.
Coordinates epoch logic: challenge generation → verification → block production → slashing.
No app.* imports.
"""
from __future__ import annotations
import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from chain.consensus.challenge import ChallengeGenerator
from chain.consensus.verifier import ChallengeVerifier
from chain.consensus.producer import BlockProducer
from chain.consensus.finalizer import BlockFinalizer
from chain.consensus.rewards import StorageRewardCalculator
from chain.consensus.registry import ValidatorRegistry
from chain.consensus.reputation import ReputationManager
from chain.consensus.slashing import SlashingManager, SlashReason
from chain.database import AsyncSessionLocal
from chain.config import settings

logger = logging.getLogger(__name__)

EPOCH_SECONDS = settings.EPOCH_SECONDS


class ConsensusManager:
    """
    Coordinates all consensus sub-engines for one epoch.

    Phase 1 slashing:
    - DOUBLE_SIGN  : same validator proposes two hashes at same height in same epoch
    - INVALID_BLOCK: block production fails validation
    - DOWNTIME     : consecutive miss streak ≥ SLASHING_DOWNTIME_SLOTS
    """

    def __init__(self, validator_key: str):
        self.validator_key = validator_key
        self.generator = ChallengeGenerator()
        self.verifier = ChallengeVerifier()
        self.producer = BlockProducer()
        self.finalizer = BlockFinalizer()
        self.reward_calc = StorageRewardCalculator()
        self.registry = ValidatorRegistry()
        self.reputation = ReputationManager()
        self.slasher = SlashingManager()

        # Double-sign detection state
        self._seen_proposals: dict[int, dict[str, str]] = defaultdict(dict)  # height -> {validator: hash}
        self._miss_streaks: dict[str, int] = {}

    async def run_epoch(self, epoch: int) -> None:
        """Execute one full consensus epoch."""
        logger.debug("[consensus] Epoch %d starting.", epoch)

        # 1. Generate storage challenges
        async with AsyncSessionLocal() as db:
            try:
                await self.generator.generate_epoch_challenges(db, epoch)
                await db.commit()
            except Exception as exc:
                logger.error("[consensus] Challenge generation failed epoch %d: %s", epoch, exc)
                await db.rollback()

        # 2. Wait for challenge response window
        await asyncio.sleep(settings.EPOCH_SECONDS * 0.6)

        # 3. Collect results and produce block
        async with AsyncSessionLocal() as db:
            try:
                results = await self.verifier.collect_epoch_results(db, epoch)
                weight = results.get("consensus_weight", 0.0)

                validators = await self.registry.get_active_validators(db)
                n_validators = len(validators)

                if weight >= 0.67:
                    ok = await self.producer.produce_block(db, epoch)
                    if ok:
                        for v in validators:
                            await self.reputation.record_produced(db, v.node_id)
                            self._miss_streaks[v.node_id] = 0
                    else:
                        # Block production failed — INVALID_BLOCK slash
                        for v in validators:
                            await self._slash(db, v.address, SlashReason.INVALID_BLOCK,
                                              f"Block production failed epoch {epoch}", epoch)
                else:
                    # Below quorum — record misses, check downtime
                    for v in validators:
                        streak = await self.reputation.record_missed(db, v.node_id)
                        self._miss_streaks[v.node_id] = streak
                        if streak >= settings.SLASHING_DOWNTIME_SLOTS:
                            await self._slash(db, v.address, SlashReason.DOWNTIME,
                                              f"Miss streak={streak} slots", epoch)
                            self._miss_streaks[v.node_id] = 0

                await db.commit()
            except Exception as exc:
                logger.error("[consensus] Epoch %d processing failed: %s", epoch, exc)
                await db.rollback()

    async def _slash(self, db, address: str, reason: SlashReason, evidence: str, slot: int) -> None:
        try:
            result = await self.slasher.check_and_slash(db, address, reason, evidence, slot)
            if result:
                logger.warning("[consensus] Slashed %s: %s", address, reason.value)
        except Exception as exc:
            logger.error("[consensus] Slash failed for %s: %s", address, exc)
