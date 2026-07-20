"""
chain/rpc/handlers.py — JSON-RPC 2.0 method handlers.
No app.* imports. Uses chain/ database and models directly.
"""
from __future__ import annotations
import logging
import time
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from chain.models import ChainBlock, ChainTransaction, ChainAccount
from chain.core.chain import VITChain
from chain.core.transaction import VITTransaction, verify_transaction
from chain.config import settings

logger = logging.getLogger(__name__)

_chain = VITChain()


def _hex(n: int) -> str:
    return hex(n)


def _vit_to_wei_hex(amount: Decimal) -> str:
    return hex(int(amount * Decimal("1000000000000000000")))


# ── Standard eth_* methods ────────────────────────────────────────────────────

async def net_version() -> str:
    return str(settings.CHAIN_ID)


async def eth_chainId() -> str:
    return hex(settings.CHAIN_ID)


async def eth_blockNumber(db: AsyncSession) -> str:
    height = await _chain.get_height(db)
    return _hex(max(0, height))


async def eth_getBalance(address: str, block: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(ChainAccount.balance).where(ChainAccount.address == address)
    )
    balance = result.scalar_one_or_none() or Decimal("0")
    return _vit_to_wei_hex(balance)


async def eth_getTransactionCount(address: str, block: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(ChainAccount.nonce).where(ChainAccount.address == address)
    )
    nonce = result.scalar_one_or_none() or 0
    return _hex(nonce)


async def eth_sendRawTransaction(raw_tx: str, db: AsyncSession) -> str:
    """
    Accept a signed raw transaction (hex-encoded JSON for VIT native txs).
    Returns tx_hash or raises on invalid.
    """
    try:
        import json
        tx_data = json.loads(bytes.fromhex(raw_tx.replace("0x", "")))
        tx = VITTransaction(
            from_address=tx_data["from"],
            to_address=tx_data["to"],
            amount=Decimal(str(tx_data.get("value", "0"))),
            nonce=int(tx_data.get("nonce", 0)),
            timestamp=int(tx_data.get("timestamp", time.time())),
            gas_fee=Decimal(str(tx_data.get("gasPrice", "0"))),
            data=tx_data.get("data"),
            signature=tx_data.get("signature", ""),
        )
        tx.tx_hash = tx.compute_hash()
        from chain.consensus.producer import mempool
        mempool.add(tx)
        return "0x" + tx.tx_hash
    except Exception as exc:
        raise ValueError(f"Invalid transaction: {exc}")


async def eth_getBlockByNumber(block_number: str, full_txs: bool, db: AsyncSession) -> dict | None:
    if block_number in ("latest", "pending"):
        block = await _chain.get_latest_block(db)
    else:
        try:
            height = int(block_number, 16) if block_number.startswith("0x") else int(block_number)
        except ValueError:
            return None
        block = await _chain.get_block_by_height(db, height)

    if not block:
        return None
    return _format_block(block, full_txs)


async def eth_getBlockByHash(block_hash: str, full_txs: bool, db: AsyncSession) -> dict | None:
    block = await _chain.get_block_by_hash(db, block_hash.replace("0x", ""))
    return _format_block(block, full_txs) if block else None


async def eth_getTransactionByHash(tx_hash: str, db: AsyncSession) -> dict | None:
    tx = await _chain.get_transaction(db, tx_hash.replace("0x", ""))
    if not tx:
        return None
    return {
        "hash": "0x" + tx["tx_hash"],
        "from": tx.get("from_address"),
        "to": tx.get("to_address"),
        "value": _vit_to_wei_hex(Decimal(str(tx.get("amount", "0")))),
        "nonce": _hex(tx.get("nonce", 0)),
        "gas": "0x5208",
        "gasPrice": _hex(settings.GAS_PRICE_WEI),
        "blockNumber": _hex(tx["block_height"]) if tx.get("block_height") is not None else None,
    }


async def eth_getTransactionReceipt(tx_hash: str, db: AsyncSession) -> dict | None:
    tx = await _chain.get_transaction(db, tx_hash.replace("0x", ""))
    if not tx or not tx.get("block_height"):
        return None
    return {
        "transactionHash": "0x" + tx["tx_hash"],
        "blockNumber": _hex(tx["block_height"]),
        "status": "0x1" if tx.get("status") == "confirmed" else "0x0",
        "from": tx.get("from_address"),
        "to": tx.get("to_address"),
        "gasUsed": "0x5208",
        "logs": [],
    }


async def eth_call(call_object: dict, block: str, db: AsyncSession) -> str:
    return "0x"


async def eth_gasPrice() -> str:
    return _hex(settings.GAS_PRICE_WEI)


async def eth_estimateGas(call_object: dict) -> str:
    return "0x5208"


async def eth_getLogs(filter_obj: dict, db: AsyncSession) -> list:
    return []


async def web3_clientVersion() -> str:
    return f"VITChain/{settings.NODE_VERSION}/python"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_block(block, full_txs: bool) -> dict:
    return {
        "number": _hex(block.height),
        "hash": "0x" + block.block_hash,
        "parentHash": "0x" + block.prev_hash,
        "miner": block.validator_id,
        "timestamp": _hex(block.timestamp),
        "transactions": [tx.to_dict() for tx in block.transactions] if full_txs
                        else ["0x" + tx.tx_hash for tx in block.transactions if tx.tx_hash],
        "transactionCount": block.tx_count,
        "gasLimit": "0xffffffff",
        "gasUsed": "0x0",
        "difficulty": "0x1",
        "totalDifficulty": "0x1",
        "size": "0x100",
        "nonce": "0x0000000000000000",
        "extraData": "0x",
        "logsBloom": "0x" + "0" * 512,
        "receiptsRoot": "0x" + block.merkle_root,
        "stateRoot": "0x" + "0" * 64,
        "sha3Uncles": "0x" + "0" * 64,
        "uncles": [],
    }
