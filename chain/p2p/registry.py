"""
chain/p2p/registry.py — PeerRegistry: persists known peers.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from chain.models import PeerNode

logger = logging.getLogger(__name__)


class PeerRegistry:

    async def upsert(self, db: AsyncSession, node_id: str,
                     ws_url: str = "", http_url: str = "", metadata: dict = None) -> PeerNode:
        result = await db.execute(select(PeerNode).where(PeerNode.node_id == node_id))
        peer = result.scalar_one_or_none()
        if peer:
            peer.ws_url = ws_url or peer.ws_url
            peer.http_url = http_url or peer.http_url
            peer.status = "active"
            peer.last_seen = datetime.now(timezone.utc)
        else:
            peer = PeerNode(node_id=node_id, ws_url=ws_url, http_url=http_url,
                            status="active", metadata=metadata or {})
            db.add(peer)
        await db.flush()
        return peer

    async def get_active_peers(self, db: AsyncSession, limit: int = 50,
                                exclude: list[str] = None) -> list[PeerNode]:
        stmt = select(PeerNode).where(PeerNode.status == "active")
        if exclude:
            stmt = stmt.where(PeerNode.node_id.not_in(exclude))
        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def mark_disconnected(self, db: AsyncSession, node_id: str) -> None:
        await db.execute(
            update(PeerNode).where(PeerNode.node_id == node_id).values(status="disconnected")
        )

    async def count_active(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(PeerNode).where(PeerNode.status == "active")
        )
        return len(result.scalars().all())
