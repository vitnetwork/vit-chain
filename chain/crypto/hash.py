import hashlib
from eth_hash.auto import keccak


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def keccak256_hex(data: bytes) -> str:
    return keccak(data).hex()


def double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash_block_header(
    prev_hash: str,
    merkle_root: str,
    timestamp: int,
    height: int,
    validator_id: str,
    version: int = 1,
    nonce: int = 0,
) -> str:
    """Canonical, deterministic block header hash."""
    header = f"{version}:{prev_hash}:{merkle_root}:{timestamp}:{height}:{validator_id}:{nonce}"
    return sha256_hex(header.encode("utf-8"))
