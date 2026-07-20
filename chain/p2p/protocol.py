"""
chain/p2p/protocol.py — P2P message types and serialisation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import json
import time


class MsgType:
    HELLO        = "hello"
    PING         = "ping"
    PONG         = "pong"
    NEW_BLOCK    = "new_block"
    NEW_TX       = "new_tx"
    GET_PEERS    = "get_peers"
    PEERS        = "peers"
    GET_BLOCKS   = "get_blocks"
    BLOCKS       = "blocks"
    RELAY_REQ    = "relay_request"
    RELAY_INTRO  = "relay_intro"
    DISCONNECT   = "disconnect"


@dataclass
class P2PMessage:
    type: str
    payload: dict = field(default_factory=dict)
    sender_node_id: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "payload": self.payload,
            "sender": self.sender_node_id,
            "ts": self.timestamp,
        })

    @staticmethod
    def from_json(raw: str) -> "P2PMessage":
        d = json.loads(raw)
        return P2PMessage(
            type=d.get("type", ""),
            payload=d.get("payload", {}),
            sender_node_id=d.get("sender", ""),
            timestamp=d.get("ts", int(time.time())),
        )
