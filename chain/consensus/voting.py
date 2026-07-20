"""
chain/consensus/voting.py — VoteCollector: in-memory vote aggregation per epoch.
"""
from __future__ import annotations
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class VoteCollector:
    def __init__(self):
        self._votes: dict[int, dict[str, str]] = defaultdict(dict)  # epoch -> {node_id: block_hash}

    def cast_vote(self, epoch: int, node_id: str, block_hash: str) -> None:
        self._votes[epoch][node_id] = block_hash

    def get_quorum(self, epoch: int, threshold: float = 0.67) -> str | None:
        """Return the block_hash that has ≥ threshold fraction of votes, or None."""
        votes = self._votes.get(epoch, {})
        if not votes:
            return None
        counts: dict[str, int] = {}
        for bh in votes.values():
            counts[bh] = counts.get(bh, 0) + 1
        total = len(votes)
        for bh, count in counts.items():
            if count / total >= threshold:
                return bh
        return None

    def clear_epoch(self, epoch: int) -> None:
        self._votes.pop(epoch, None)
