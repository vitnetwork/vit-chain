"""
chain/rpc/router.py — FastAPI router for JSON-RPC 2.0 at POST /rpc.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from chain.database import get_db
from chain.rpc.server import rpc_server
from chain.config import settings

router = APIRouter(tags=["JSON-RPC"])


@router.post("/rpc")
async def rpc_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """
    JSON-RPC 2.0 endpoint — MetaMask compatible.
    Supports both single requests and batch arrays.
    """
    body = await request.json()
    if isinstance(body, list):
        return await rpc_server.handle_batch(body, db)
    return await rpc_server.handle(body, db)


@router.get("/rpc")
async def rpc_health():
    """MetaMask network health probe."""
    return {
        "status": "ok",
        "chain_id": settings.CHAIN_ID,
        "network": settings.NETWORK,
        "name": "VIT Chain",
        "jsonrpc": "2.0",
    }


@router.get("/rpc/health")
async def rpc_health_detail():
    """Compatibility health endpoint used by wallet tooling."""
    return {
        "status": "ok",
        "chain_id": settings.CHAIN_ID,
        "network": settings.NETWORK,
        "name": "VIT Chain",
    }


@router.post("/api/chain/rpc")
async def rpc_endpoint_compat(request: Request, db: AsyncSession = Depends(get_db)):
    """Backward-compatible chain RPC alias used by gateway clients."""
    body = await request.json()
    if isinstance(body, list):
        return await rpc_server.handle_batch(body, db)
    return await rpc_server.handle(body, db)


@router.get("/api/chain/rpc")
async def rpc_health_compat():
    """Backward-compatible chain RPC health alias."""
    return {
        "status": "ok",
        "chain_id": settings.CHAIN_ID,
        "network": settings.NETWORK,
        "name": "VIT Chain",
        "jsonrpc": "2.0",
    }


@router.get("/api/chain/rpc/health")
async def rpc_health_compat_detail():
    """Health detail alias used by chain clients and monitoring."""
    return {
        "status": "ok",
        "chain_id": settings.CHAIN_ID,
        "network": settings.NETWORK,
        "name": "VIT Chain",
    }
