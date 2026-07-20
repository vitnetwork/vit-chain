"""
chain/p2p/bootstrap.py — BootstrapManager: discovers initial peers.
"""
from __future__ import annotations
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from chain.config import settings
from chain.p2p.registry import PeerRegistry

logger = logging.getLogger(__name__)


class BootstrapManager:

    def __init__(self):
        self.registry = PeerRegistry()
        self._bootstrap_nodes = []
        if settings.VIT_BOOTSTRAP_HTTP_URL:
            self._bootstrap_nodes.append({
                "node_id": "VIT_BOOTSTRAP_1",
                "ws_url": settings.VIT_BOOTSTRAP_WS_URL,
                "http_url": settings.VIT_BOOTSTRAP_HTTP_URL,
            })

    async def get_initial_peers(self, our_node_id: str) -> list[dict]:
        """Connect to bootstrap nodes and collect peer lists via HTTP."""
        if not self._bootstrap_nodes:
            return []
        all_peers = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                for node in self._bootstrap_nodes:
                    try:
                        async with session.get(node["http_url"], timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                peers = await resp.json()
                                if isinstance(peers, list):
                                    all_peers.extend(peers)
                    except Exception as exc:
                        logger.debug("[bootstrap] Peer fetch failed from %s: %s", node["http_url"], exc)
        except ImportError:
            pass

        seen = {our_node_id}
        unique = []
        for p in all_peers:
            if p.get("node_id") not in seen:
                unique.append(p)
                seen.add(p["node_id"])
        return unique[:20]

    async def serve_peer_list(self, db: AsyncSession, requester_node_id: str) -> list[dict]:
        peers = await self.registry.get_active_peers(db, limit=50, exclude=[requester_node_id])
        return [{"node_id": p.node_id, "ws_url": p.ws_url, "http_url": p.http_url} for p in peers]
