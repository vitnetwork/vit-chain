"""
chain/core/transaction.py — VITTransaction and Mempool.
No app.* imports.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Callable

from chain.crypto.hash import keccak256_hex
from chain.crypto.ecdsa import sign, recover_public_key
from chain.crypto.address import public_key_to_address, ZERO_ADDRESS


@dataclass
class VITTransaction:
    from_address: str
    to_address: str
    amount: Decimal
    nonce: int
    timestamp: int
    gas_fee: Decimal = field(default_factory=lambda: Decimal("0"))
    data: Optional[dict] = None
    signature: str = ""
    tx_hash: str = ""
    status: str = "pending"

    def compute_hash(self) -> str:
        raw = (
            f"{self.from_address}:{self.to_address}:{self.amount}:"
            f"{self.nonce}:{self.timestamp}:{self.gas_fee}"
        )
        return keccak256_hex(raw.encode("utf-8"))

    def sign(self, private_key_hex: str) -> None:
        self.tx_hash = self.compute_hash()
        self.signature = sign(self.tx_hash, private_key_hex)

    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount": str(self.amount),
            "nonce": self.nonce,
            "timestamp": self.timestamp,
            "gas_fee": str(self.gas_fee),
            "data": self.data,
            "signature": self.signature,
            "status": self.status,
        }


def create_transaction(
    from_address: str,
    to_address: str,
    amount: Decimal,
    nonce: int,
    private_key_hex: str,
    gas_fee: Decimal = Decimal("0"),
    data: Optional[dict] = None,
) -> VITTransaction:
    tx = VITTransaction(
        from_address=from_address,
        to_address=to_address,
        amount=amount,
        nonce=nonce,
        timestamp=int(time.time()),
        gas_fee=gas_fee,
        data=data,
    )
    tx.sign(private_key_hex)
    return tx


def verify_transaction(tx: VITTransaction, additional_verify: Optional[Callable] = None) -> bool:
    """Verify tx hash integrity and ECDSA signature."""
    if not tx.tx_hash:
        return False
    if tx.from_address == ZERO_ADDRESS:
        return True  # Genesis mints bypass verification
    if not tx.signature:
        return False
    recovered_pub = recover_public_key(bytes.fromhex(tx.tx_hash), tx.signature)
    if not recovered_pub:
        return False
    if public_key_to_address(recovered_pub) != tx.from_address:
        return False
    if additional_verify and not additional_verify(tx):
        return False
    return True


class Mempool:
    """In-process transaction pool — not persisted across restarts."""

    def __init__(self, max_size: int = 5000, tx_ttl: int = 3600):
        self._transactions: dict[str, VITTransaction] = {}
        self.max_size = max_size
        self.tx_ttl = tx_ttl

    def add(self, tx: VITTransaction, additional_verify: Optional[Callable] = None) -> bool:
        if tx.tx_hash in self._transactions:
            return False
        if len(self._transactions) >= self.max_size:
            self.clear_expired()
            if len(self._transactions) >= self.max_size:
                return False
        if time.time() - tx.timestamp > self.tx_ttl:
            return False
        if not verify_transaction(tx, additional_verify):
            return False
        self._transactions[tx.tx_hash] = tx
        return True

    # Alias
    def add_transaction(self, tx: VITTransaction, additional_verify: Optional[Callable] = None) -> bool:
        return self.add(tx, additional_verify)

    def clear_expired(self) -> None:
        now = time.time()
        expired = [h for h, tx in self._transactions.items() if now - tx.timestamp > self.tx_ttl]
        for h in expired:
            del self._transactions[h]

    def get_pending(self, limit: int = 500) -> list[VITTransaction]:
        self.clear_expired()
        return sorted(self._transactions.values(), key=lambda t: t.gas_fee, reverse=True)[:limit]

    def remove(self, tx_hashes: list[str]) -> None:
        for h in tx_hashes:
            self._transactions.pop(h, None)

    def get(self, tx_hash: str) -> Optional[VITTransaction]:
        return self._transactions.get(tx_hash)

    def contains(self, tx_hash: str) -> bool:
        return tx_hash in self._transactions

    def size(self) -> int:
        return len(self._transactions)
