#!/usr/bin/env python3
"""
scripts/generate_wallet.py
Generates a fresh VIT wallet keypair for use as GENESIS_TREASURY_KEY / VIT_VALIDATOR_KEY.

Usage:
    python scripts/generate_wallet.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chain.crypto.ecdsa import generate_keypair
from chain.crypto.address import public_key_to_address, format_node_id

def main():
    priv, pub = generate_keypair()
    address = public_key_to_address(pub)
    node_id = format_node_id(address)

    print("\n" + "="*60)
    print("  VIT Chain — New Wallet")
    print("="*60)
    print(f"  Private Key : {priv}")
    print(f"  Public Key  : {pub[:40]}...")
    print(f"  Address     : {address}")
    print(f"  Node ID     : {node_id}")
    print("="*60)
    print("\nRender env vars to set:")
    print(f"  GENESIS_TREASURY_KEY={priv}")
    print(f"  VIT_VALIDATOR_KEY={priv}")
    print(f"  GENESIS_PROPOSER_ADDRESS={address}")
    print(f"  VIT_NODE_ID={node_id}")
    print(f"  GENESIS_VALIDATORS={address}:1000000:genesis-validator")
    print("\n⚠  Store the private key securely — never commit it.\n")

if __name__ == "__main__":
    main()
