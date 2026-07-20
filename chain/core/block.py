"""
chain/core/block.py — VITBlock dataclass, build_block, validate_block.
No app.* imports.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Callable

from chain.crypto.hash import hash_block_header
from chain.crypto.merkle import build_transaction_merkle
from chain.crypto.ecdsa import sign, recover_public_key
from chain.crypto.address import public_key_to_address


@dataclass
class VITBlock:
    height: int
    prev_hash: str
    merkle_root: str
    timestamp: int
    validator_id: str          # VIT address of the block producer
    transactions: list         # list[VITTransaction]
    tx_count: int = 0
    total_fees: Decimal = field(default_factory=lambda: Decimal("0"))
    block_reward: Decimal = field(default_factory=lambda: Decimal("10"))
    validator_signature: str = ""
    block_hash: str = ""
    storage_proofs: list = field(default_factory=list)
    consensus_votes: list = field(default_factory=list)

    def compute_hash(self) -> str:
        tx_hashes = [tx.tx_hash for tx in self.transactions if tx.tx_hash]
        merkle = build_transaction_merkle(tx_hashes) if tx_hashes else self.merkle_root
        return hash_block_header(
            prev_hash=self.prev_hash,
            merkle_root=merkle,
            timestamp=self.timestamp,
            height=self.height,
            validator_id=self.validator_id,
        )

    def to_dict(self) -> dict:
        return {
            "height": self.height,
            "block_hash": self.block_hash,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "validator_id": self.validator_id,
            "tx_count": self.tx_count,
            "total_fees": str(self.total_fees),
            "block_reward": str(self.block_reward),
            "validator_signature": self.validator_signature,
            "storage_proofs": self.storage_proofs,
            "consensus_votes": self.consensus_votes,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }


def build_block(
    prev_block: Optional[VITBlock],
    transactions: list,
    storage_proofs: list,
    validator_key: str,
    height: int,
    timestamp: Optional[int] = None,
) -> VITBlock:
    """Build and sign a new block."""
    from chain.crypto.address import private_key_to_address

    if timestamp is None:
        timestamp = int(time.time())

    prev_hash = prev_block.block_hash if prev_block else "0" * 64
    validator_id = private_key_to_address(validator_key)
    tx_hashes = [tx.tx_hash for tx in transactions if tx.tx_hash]
    merkle_root = build_transaction_merkle(tx_hashes) if tx_hashes else hash_block_header(
        "empty", "empty", timestamp, height, validator_id
    )

    total_fees = sum((tx.gas_fee for tx in transactions), Decimal("0"))
    from chain.config import settings
    block_reward = Decimal(str(settings.BLOCK_REWARD_VIT))

    block = VITBlock(
        height=height,
        prev_hash=prev_hash,
        merkle_root=merkle_root,
        timestamp=timestamp,
        validator_id=validator_id,
        transactions=transactions,
        tx_count=len(transactions),
        total_fees=total_fees,
        block_reward=block_reward,
        storage_proofs=storage_proofs,
    )

    block.block_hash = block.compute_hash()
    block.validator_signature = sign(block.block_hash, validator_key)
    return block


def validate_block(
    block: VITBlock,
    prev_block: Optional[VITBlock],
    known_validators: Optional[list[str]] = None,
    consensus_validator: Optional[Callable] = None,
) -> bool:
    """Validate block structure, linkage, signature, and Merkle root."""
    from chain.crypto.merkle import MerkleTree

    # Height and prev_hash linkage
    if prev_block:
        if block.height != prev_block.height + 1:
            return False
        if block.prev_hash != prev_block.block_hash:
            return False
    else:
        if block.height != 0:
            return False
        if block.prev_hash != "0" * 64:
            return False

    # Hash integrity
    if block.block_hash != block.compute_hash():
        return False

    # Validator set check
    if known_validators is not None and block.validator_id not in known_validators:
        return False

    # Signature verification
    if block.validator_signature:
        recovered_pub = recover_public_key(bytes.fromhex(block.block_hash), block.validator_signature)
        if not recovered_pub:
            return False
        if public_key_to_address(recovered_pub) != block.validator_id:
            return False

    # Timestamp must advance
    if prev_block and block.timestamp <= prev_block.timestamp:
        return False

    # Custom consensus validator
    if consensus_validator and not consensus_validator(block):
        return False

    return True
