#!/usr/bin/env python3
"""
scripts/seed_genesis.py — Force-seed the genesis block (idempotent).
Run this if the genesis block is missing after a DB reset.

Usage:
    python scripts/seed_genesis.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from chain.database import init_db, AsyncSessionLocal
from chain.genesis import ensure_genesis


async def main():
    print("Initialising database…")
    await init_db()
    async with AsyncSessionLocal() as db:
        block = await ensure_genesis(db)
        await db.commit()
        print(f"Genesis block: height={block.height} hash={block.block_hash}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
