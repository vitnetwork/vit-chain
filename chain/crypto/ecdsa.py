"""
chain/crypto/ecdsa.py — ECDSA helpers using coincurve (secp256k1).
All coincurve imports are lazy (inside functions) to avoid module-level
import failures before the uvicorn event loop is running.
"""
from __future__ import annotations


def generate_keypair() -> tuple[str, str]:
    """Returns (private_key_hex, public_key_hex) uncompressed secp256k1."""
    from coincurve import PrivateKey
    priv = PrivateKey()
    pub = priv.public_key.format(compressed=False).hex()
    return priv.secret.hex(), pub


def sign(message_hash_hex: str, private_key_hex: str) -> str:
    """Sign a 32-byte message hash; returns DER signature hex."""
    from coincurve import PrivateKey
    priv = PrivateKey.from_hex(private_key_hex)
    sig = priv.sign(bytes.fromhex(message_hash_hex), hasher=None)
    return sig.hex()


def recover_public_key(message_hash: bytes, signature_hex: str) -> str | None:
    """Recover uncompressed public key hex from signature; None on failure."""
    from coincurve import PublicKey
    try:
        sig_bytes = bytes.fromhex(signature_hex)
        pub = PublicKey.from_signature_and_message(sig_bytes, message_hash, hasher=None)
        return pub.format(compressed=False).hex()
    except Exception:
        return None


def verify_signature(message_hash_hex: str, signature_hex: str, public_key_hex: str) -> bool:
    """Verify a DER signature against a public key for a message hash."""
    from coincurve import PublicKey
    try:
        pub = PublicKey(bytes.fromhex(public_key_hex))
        sig_bytes = bytes.fromhex(signature_hex)
        return pub.verify(sig_bytes, bytes.fromhex(message_hash_hex), hasher=None)
    except Exception:
        return False
