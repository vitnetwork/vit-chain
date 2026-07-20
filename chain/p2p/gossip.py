"""
chain/p2p/gossip.py — GossipProtocol: WebSocket peer message handling.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any
from chain.p2p.protocol import P2PMessage, MsgType

logger = logging.getLogger(__name__)

# Active WebSocket connections: node_id -> websocket
_connections: dict[str, Any] = {}


def register_connection(node_id: str, ws: Any) -> None:
    _connections[node_id] = ws
    logger.info("[gossip] Peer connected: %s (total=%d)", node_id, len(_connections))


def remove_connection(node_id: str) -> None:
    _connections.pop(node_id, None)
    logger.info("[gossip] Peer disconnected: %s (total=%d)", node_id, len(_connections))


async def broadcast(msg: P2PMessage, exclude: list[str] = None) -> None:
    """Broadcast a message to all connected peers except excluded ones."""
    exclude = exclude or []
    payload = msg.to_json()
    dead = []
    for node_id, ws in list(_connections.items()):
        if node_id in exclude:
            continue
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(node_id)
    for node_id in dead:
        remove_connection(node_id)


async def send_to(node_id: str, msg: P2PMessage) -> bool:
    ws = _connections.get(node_id)
    if not ws:
        return False
    try:
        await ws.send_text(msg.to_json())
        return True
    except Exception:
        remove_connection(node_id)
        return False


def peer_count() -> int:
    return len(_connections)


async def handle_message(raw: str, sender_node_id: str) -> None:
    """Process an incoming P2P message."""
    try:
        msg = P2PMessage.from_json(raw)
    except Exception as exc:
        logger.warning("[gossip] Malformed message from %s: %s", sender_node_id, exc)
        return

    if msg.type == MsgType.PING:
        await send_to(sender_node_id, P2PMessage(type=MsgType.PONG, sender_node_id="self"))

    elif msg.type == MsgType.NEW_BLOCK:
        logger.info("[gossip] New block announced by %s: height=%s",
                    sender_node_id, msg.payload.get("height"))
        # Relay to other peers
        msg.sender_node_id = sender_node_id
        await broadcast(msg, exclude=[sender_node_id])

    elif msg.type == MsgType.NEW_TX:
        logger.debug("[gossip] New tx from %s: %s", sender_node_id, msg.payload.get("tx_hash"))
        await broadcast(msg, exclude=[sender_node_id])

    elif msg.type == MsgType.DISCONNECT:
        remove_connection(sender_node_id)
