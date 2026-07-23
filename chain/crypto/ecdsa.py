"""
chain/crypto/ecdsa.py — ECDSA helpers using coincurve (secp256k1).
All coincurve imports are lazy (inside functions) to avoid module-level
import failures before the uvicorn event loop is running.

Signature format: 65-byte recoverable (compact) — sign_recoverable / from_signature_and_message.
DER format is NOT used because DER signatures cannot be used to recover the public key.
"""
from __future__ import annotations


def generate_keypair() -> tuple[str, str]:
    """Returns (private_key_hex, public_key_hex) uncompressed secp256k1."""
    from coincurve import PrivateKey
    priv = PrivateKey()
    pub = priv.public_key.format(compressed=False).hex()
    return priv.secret.hex(), pub


def sign(message_hash_hex: str, private_key_hex: str) -> str:
    """Sign a 32-byte message hash.

    Returns a 65-byte recoverable signature as hex (compact format: r || s || v).
    This format is required so recover_public_key() can reconstruct the signer's
    public key from the signature alone — which validate_block() depends on.
    """
    from coincurve import PrivateKey
    priv = PrivateKey.from_hex(private_key_hex)
    sig = priv.sign_recoverable(bytes.fromhex(message_hash_hex), hasher=None)
    return sig.hex()


def recover_public_key(message_hash: bytes, signature_hex: str) -> str | None:
    """Recover uncompressed public key hex from a 65-byte recoverable signature.

    Returns None on any failure (bad signature, wrong format, etc.).
    """
    from coincurve import PublicKey
    try:
        sig_bytes = bytes.fromhex(signature_hex)
        pub = PublicKey.from_signature_and_message(sig_bytes, message_hash, hasher=None)
        return pub.format(compressed=False).hex()
    except Exception:
        return None


def verify_signature(message_hash_hex: str, signature_hex: str, public_key_hex: str) -> bool:
    """Verify a recoverable signature against a known public key for a message hash.

    Verifies by recovering the public key and comparing — works with recoverable signatures.
    """
    try:
        recovered = recover_public_key(bytes.fromhex(message_hash_hex), signature_hex)
        if not recovered:
            return False
        # Normalise the expected key (strip 04 prefix if present for comparison)
        expected = public_key_hex
        if expected.startswith("04"):
            expected = expected[2:]
        rec = recovered
        if rec.startswith("04"):
            rec = rec[2:]
        return rec == expected
    except Exception:
        return False
