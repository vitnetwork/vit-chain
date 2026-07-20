"""
api/peers.py — P2P peer list and WebSocket gossip endpoint.
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from chain.database import get_db, AsyncSessionLocal
from chain.p2p.registry import PeerRegistry
from chain.p2p.gossip import (
    register_connection, remove_connection, handle_message, peer_count
)
from chain.config import settings

router = APIRouter(prefix="/api", tags=["P2P"])
_reg = PeerRegistry()


@router.get("/peers")
async def list_peers(db: AsyncSession = Depends(get_db)):
    peers = await _reg.get_active_peers(db, limit=50)
    return {
        "connected": peer_count(),
        "known": len(peers),
        "peers": [
            {
                "node_id": p.node_id,
                "ws_url": p.ws_url,
                "http_url": p.http_url,
                "status": p.status,
            }
            for p in peers
        ],
    }


@router.websocket("/peer")
async def peer_ws(ws: WebSocket):
    """P2P gossip WebSocket — peers connect here to join the network."""
    await ws.accept()
    node_id = None
    try:
        # Expect HELLO as first message: {"type":"hello","payload":{"node_id":"did:vit:0x..."}}
        raw = await ws.receive_text()
        from chain.p2p.protocol import P2PMessage, MsgType
        msg = P2PMessage.from_json(raw)
        if msg.type != MsgType.HELLO:
            await ws.close(code=4000)
            return

        node_id = msg.payload.get("node_id", "anonymous")
        ws_url = msg.payload.get("ws_url", "")
        http_url = msg.payload.get("http_url", "")

        register_connection(node_id, ws)

        # Persist peer
        async with AsyncSessionLocal() as db:
            await _reg.upsert(db, node_id=node_id, ws_url=ws_url, http_url=http_url)
            await db.commit()

        # Respond with our node info
        import json
        await ws.send_text(json.dumps({
            "type": MsgType.HELLO,
            "payload": {
                "node_id": settings.VIT_NODE_ID or "vit-chain-node",
                "chain_id": settings.CHAIN_ID,
                "network": settings.NETWORK,
            }
        }))

        # Message loop
        while True:
            raw = await ws.receive_text()
            await handle_message(raw, node_id)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if node_id:
            remove_connection(node_id)
            async with AsyncSessionLocal() as db:
                await _reg.mark_disconnected(db, node_id)
                await db.commit()
