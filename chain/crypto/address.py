from .hash import keccak256_hex

ZERO_ADDRESS = "0x" + "0" * 40


def public_key_to_address(public_key_hex: str) -> str:
    """
    Derive VIT address from uncompressed public key.
    Strips 04 prefix, keccak256 the 64-byte key, take last 20 bytes.
    Returns checksum-style 0x-prefixed hex.
    """
    if public_key_hex.startswith("04"):
        public_key_hex = public_key_hex[2:]
    pub_bytes = bytes.fromhex(public_key_hex)
    digest = keccak256_hex(pub_bytes)
    return "0x" + digest[-40:]


def private_key_to_address(private_key_hex: str) -> str:
    """Derive VIT address directly from a private key hex string."""
    from coincurve import PrivateKey
    priv = PrivateKey.from_hex(private_key_hex)
    pub_hex = priv.public_key.format(compressed=False).hex()
    return public_key_to_address(pub_hex)


def format_node_id(address: str) -> str:
    """Format address as DID: did:vit:<address>"""
    if not address.startswith("0x"):
        address = "0x" + address
    return f"did:vit:{address}"
