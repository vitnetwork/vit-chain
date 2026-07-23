"""
chain/consensus/producer.py — BlockProducer: assembles and submits new blocks.
"""
from __future__ import annotations
import logging
import time
from sqlalchemy.ext.asyncio import AsyncSession

from chain.core.chain import VITChain
from chain.core.block import build_block
from chain.core.transaction import Mempool
from chain.config import settings

logger = logging.getLogger(__name__)

# Module-level mempool shared across the process
mempool = Mempool(max_size=5000, tx_ttl=3600)


class BlockProducer:

    def __init__(self):
        self._chain = VITChain()

    async def produce_block(self, db: AsyncSession, epoch: int) -> bool:
        validator_key = settings.VIT_VALIDATOR_KEY.strip()
        if not validator_key:
            validator_key = settings.GENESIS_TREASURY_KEY.strip()
        if not validator_key:
            if settings.NETWORK == "mainnet":
                logger.warning("[producer] No validator key on mainnet — cannot produce block.")
                return False
            import hashlib
            validator_key = hashlib.sha256(
                f"vit-{settings.NETWORK}-validator-1-{settings.CHAIN_ID}".encode()
            ).hexdigest()
            logger.warning(
                "[producer] VIT_VALIDATOR_KEY not set — using auto-generated deterministic key "
                "(testnet only). Set this env var for a stable validator identity."
            )

        latest = await self._chain.get_latest_block(db)
        height = (latest.height + 1) if latest else 0

        pending_txs = mempool.get_pending(limit=500)

        block = build_block(
            prev_block=latest,
            transactions=pending_txs,
            storage_proofs=[],
            validator_key=validator_key,
            height=height,
            timestamp=int(time.time()),
        )

        ok = await self._chain.add_block(db, block)
        if ok:
            mempool.remove([tx.tx_hash for tx in pending_txs])
            logger.info("[producer] Block %d produced: %s…", height, block.block_hash[:16])

            # Publish to cache channel
            from chain.cache import cache_publish
            import json
            await cache_publish(
                f"vit:consensus:produce_block:{epoch}",
                json.dumps({"height": height, "hash": block.block_hash, "epoch": epoch}),
            )

        return ok
