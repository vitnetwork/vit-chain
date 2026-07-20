"""
chain/core/state.py — ChainState: applies transactions to ChainAccount balances.
No app.* imports.
"""
import logging
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from chain.models import ChainAccount
from chain.core.transaction import VITTransaction

logger = logging.getLogger(__name__)


class ChainState:
    """Applies block transactions to persistent ChainAccount state."""

    async def get_or_create_account(self, db: AsyncSession, address: str) -> ChainAccount:
        result = await db.execute(select(ChainAccount).where(ChainAccount.address == address))
        account = result.scalar_one_or_none()
        if not account:
            account = ChainAccount(address=address, balance=Decimal("0"), staked=Decimal("0"), nonce=0)
            db.add(account)
            await db.flush()
        return account

    async def apply_transaction(self, db: AsyncSession, tx: VITTransaction, block_height: int = 0) -> bool:
        from chain.crypto.address import ZERO_ADDRESS

        try:
            to_acc = await self.get_or_create_account(db, tx.to_address)

            if tx.from_address and tx.from_address != ZERO_ADDRESS:
                from_acc = await self.get_or_create_account(db, tx.from_address)
                required = tx.amount + tx.gas_fee
                if from_acc.balance < required:
                    logger.warning("Insufficient balance: %s has %s, needs %s",
                                   tx.from_address, from_acc.balance, required)
                    return False
                from_acc.balance -= required
                from_acc.nonce = max(from_acc.nonce, tx.nonce + 1)
                if block_height:
                    from_acc.last_active_height = block_height

            to_acc.balance += tx.amount
            if not to_acc.first_seen_height and block_height:
                to_acc.first_seen_height = block_height
            if block_height:
                to_acc.last_active_height = block_height

            await db.flush()
            return True
        except Exception as exc:
            logger.error("apply_transaction failed for %s: %s", tx.tx_hash, exc)
            return False

    async def apply_block_reward(self, db: AsyncSession, validator_address: str,
                                  reward: Decimal, block_height: int = 0) -> None:
        acc = await self.get_or_create_account(db, validator_address)
        acc.balance += reward
        if block_height:
            acc.last_active_height = block_height
        await db.flush()
