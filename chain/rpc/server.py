"""
chain/rpc/server.py — JSON-RPC 2.0 dispatcher.
"""
from __future__ import annotations
import inspect
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from chain.rpc import handlers

logger = logging.getLogger(__name__)

_METHODS = {
    "net_version":                 handlers.net_version,
    "eth_chainId":                 handlers.eth_chainId,
    "eth_blockNumber":             handlers.eth_blockNumber,
    "eth_getBalance":              handlers.eth_getBalance,
    "eth_getTransactionCount":     handlers.eth_getTransactionCount,
    "eth_sendRawTransaction":      handlers.eth_sendRawTransaction,
    "eth_getBlockByNumber":        handlers.eth_getBlockByNumber,
    "eth_getBlockByHash":          handlers.eth_getBlockByHash,
    "eth_getTransactionByHash":    handlers.eth_getTransactionByHash,
    "eth_getTransactionReceipt":   handlers.eth_getTransactionReceipt,
    "eth_call":                    handlers.eth_call,
    "eth_gasPrice":                handlers.eth_gasPrice,
    "eth_estimateGas":             handlers.eth_estimateGas,
    "eth_getLogs":                 handlers.eth_getLogs,
    "web3_clientVersion":          handlers.web3_clientVersion,
}


class VITChainRPC:

    async def handle(self, request: dict, db: AsyncSession) -> dict:
        rid = request.get("id")
        method_name = request.get("method", "")
        params = request.get("params") or []

        handler = _METHODS.get(method_name)
        if not handler:
            return self._error(rid, -32601, f"Method not found: {method_name}")

        try:
            sig = inspect.signature(handler)
            call_args = list(params)
            if "db" in sig.parameters:
                result = await handler(*call_args, db=db)
            else:
                result = await handler(*call_args)
            return {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as exc:
            logger.warning("[rpc] %s failed: %s", method_name, exc)
            return self._error(rid, -32603, str(exc))

    async def handle_batch(self, requests: list[dict], db: AsyncSession) -> list[dict]:
        return [await self.handle(req, db) for req in requests]

    def _error(self, rid, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


rpc_server = VITChainRPC()
