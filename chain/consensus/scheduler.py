"""
chain/consensus/scheduler.py — EpochScheduler: drives 15-second consensus epochs.
No app.* imports.
"""
from __future__ import annotations
import asyncio
import logging
import time

from chain.config import settings
from chain.consensus.engine import ConsensusManager

logger = logging.getLogger(__name__)


class EpochScheduler:

    def __init__(self):
        self._manager: ConsensusManager | None = None
        self._running = False

    def _get_manager(self) -> ConsensusManager:
        if self._manager is None:
            validator_key = settings.VIT_VALIDATOR_KEY.strip() or settings.GENESIS_TREASURY_KEY.strip()
            if not validator_key:
                logger.warning("[scheduler] No validator key — consensus will run in observer mode.")
                validator_key = ""
            self._manager = ConsensusManager(validator_key=validator_key)
        return self._manager

    async def run(self) -> None:
        """Infinite loop — wake at epoch boundaries and run consensus."""
        self._running = True
        logger.info("[scheduler] EpochScheduler started (epoch=%ds).", settings.EPOCH_SECONDS)

        try:
            while self._running:
                now = time.time()
                epoch_len = settings.EPOCH_SECONDS
                next_epoch_start = (int(now // epoch_len) + 1) * epoch_len
                sleep_for = next_epoch_start - now

                await asyncio.sleep(sleep_for)

                current_epoch = int(time.time() // epoch_len)

                try:
                    manager = self._get_manager()
                    await manager.run_epoch(current_epoch)
                except Exception as exc:
                    logger.error("[scheduler] Epoch %d failed: %s", current_epoch, exc)

        except asyncio.CancelledError:
            self._running = False
            logger.info("[scheduler] EpochScheduler stopped.")
        except Exception as exc:
            self._running = False
            logger.critical("[scheduler] EpochScheduler crashed: %s", exc)
