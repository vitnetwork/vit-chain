"""
chain/models.py — All ORM models for the standalone VIT Chain node.
Uses chain/database.py Base — no app.* imports.
"""
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, JSON,
    ForeignKey, Index, Boolean, Text,
)
from sqlalchemy.sql import func
from chain.database import Base


# ── Chain Blocks ──────────────────────────────────────────────────────────────
class ChainBlock(Base):
    __tablename__ = "chain_blocks"

    height           = Column(Integer, primary_key=True, autoincrement=False)
    block_hash       = Column(String(128), unique=True, index=True, nullable=False)
    prev_hash        = Column(String(128), index=True, nullable=False)
    merkle_root      = Column(String(128), nullable=False)
    state_root       = Column(String(128), nullable=True)
    timestamp        = Column(Integer, index=True, nullable=False)
    validator_id     = Column(String(128), index=True, nullable=False)
    validator_signature = Column(Text, nullable=True)
    tx_count         = Column(Integer, default=0)
    total_fees       = Column(Numeric(36, 18), default=Decimal("0"))
    block_reward     = Column(Numeric(36, 18), default=Decimal("0"))
    storage_proofs   = Column(JSON, default=list)
    consensus_votes  = Column(JSON, default=list)
    raw_data         = Column(JSON, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_chain_blocks_timestamp", "timestamp"),
        Index("ix_chain_blocks_validator", "validator_id"),
        {"extend_existing": True},
    )


# ── Chain Transactions ────────────────────────────────────────────────────────
class ChainTransaction(Base):
    __tablename__ = "chain_transactions"

    tx_hash      = Column(String(128), primary_key=True)
    block_height = Column(Integer, ForeignKey("chain_blocks.height"), nullable=True, index=True)
    from_address = Column(String(128), index=True, nullable=True)
    to_address   = Column(String(128), index=True, nullable=False)
    amount       = Column(Numeric(36, 18), default=Decimal("0"))
    nonce        = Column(Integer, default=0)
    gas_fee      = Column(Numeric(36, 18), default=Decimal("0"))
    tx_type      = Column(String(32), default="transfer")  # transfer|stake|reward|storage|genesis
    data         = Column(JSON, nullable=True)
    signature    = Column(Text, nullable=True)
    timestamp    = Column(Integer, index=True, nullable=False)
    status       = Column(String(20), default="confirmed", index=True)

    __table_args__ = (
        Index("ix_chain_txs_from", "from_address"),
        Index("ix_chain_txs_to", "to_address"),
        {"extend_existing": True},
    )


# ── Chain Accounts ────────────────────────────────────────────────────────────
class ChainAccount(Base):
    __tablename__ = "chain_accounts"
    __table_args__ = {"extend_existing": True}

    address           = Column(String(128), primary_key=True)
    balance           = Column(Numeric(36, 18), default=Decimal("0"))
    staked            = Column(Numeric(36, 18), default=Decimal("0"))
    nonce             = Column(Integer, default=0)
    first_seen_height = Column(Integer, nullable=True)
    last_active_height = Column(Integer, nullable=True)
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Validators ────────────────────────────────────────────────────────────────
class Validator(Base):
    __tablename__ = "chain_validators"
    __table_args__ = {"extend_existing": True}

    node_id        = Column(String(256), primary_key=True)   # did:vit:<address>
    address        = Column(String(128), unique=True, index=True, nullable=False)
    public_key     = Column(Text, nullable=True)
    stake          = Column(Numeric(36, 18), default=Decimal("0"))
    status         = Column(String(20), default="active", index=True)  # active|jailed|exited
    name           = Column(String(128), nullable=True)
    extra_metadata = Column(JSON, default=dict)
    registered_at  = Column(DateTime(timezone=True), server_default=func.now())
    last_active    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ValidatorReputation(Base):
    __tablename__ = "chain_validator_reputation"
    __table_args__ = {"extend_existing": True}

    node_id          = Column(String(256), ForeignKey("chain_validators.node_id"), primary_key=True)
    blocks_produced  = Column(Integer, default=0)
    blocks_missed    = Column(Integer, default=0)
    miss_streak      = Column(Integer, default=0)
    total_slashed    = Column(Numeric(36, 18), default=Decimal("0"))
    score            = Column(Numeric(5, 4), default=Decimal("1.0"))
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Slashing Records ──────────────────────────────────────────────────────────
class SlashRecord(Base):
    __tablename__ = "chain_slash_records"
    __table_args__ = {"extend_existing": True}

    id                = Column(Integer, primary_key=True, autoincrement=True)
    validator_address = Column(String(128), index=True, nullable=False)
    reason            = Column(String(32), nullable=False)   # DOWNTIME|DOUBLE_SIGN|INVALID_BLOCK
    slash_amount      = Column(Numeric(36, 18), default=Decimal("0"))
    stake_before      = Column(Numeric(36, 18), default=Decimal("0"))
    stake_after       = Column(Numeric(36, 18), default=Decimal("0"))
    evidence          = Column(Text, nullable=True)
    slot              = Column(Integer, default=0)
    appealed          = Column(Boolean, default=False)
    appeal_resolved   = Column(Boolean, default=False)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


# ── Storage Challenges ────────────────────────────────────────────────────────
class StorageChallenge(Base):
    __tablename__ = "chain_storage_challenges"
    __table_args__ = {"extend_existing": True}

    challenge_id      = Column(String(128), primary_key=True)
    epoch             = Column(Integer, index=True, nullable=False)
    validator_address = Column(String(128), index=True, nullable=False)
    shard_id          = Column(String(256), nullable=True)
    challenge_data    = Column(JSON, nullable=True)
    response          = Column(JSON, nullable=True)
    verified          = Column(Boolean, default=False)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at       = Column(DateTime(timezone=True), nullable=True)


# ── P2P Peers ─────────────────────────────────────────────────────────────────
class PeerNode(Base):
    __tablename__ = "chain_peers"
    __table_args__ = {"extend_existing": True}

    node_id      = Column(String(256), primary_key=True)
    ws_url       = Column(String(512), nullable=True)
    http_url     = Column(String(512), nullable=True)
    status       = Column(String(20), default="active", index=True)  # active|disconnected|banned
    last_seen    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    peer_metadata = Column("metadata", JSON, default=dict)  # 'metadata' reserved in Declarative API


# ── Consensus Checkpoints ─────────────────────────────────────────────────────
class ConsensusCheckpoint(Base):
    __tablename__ = "chain_consensus_checkpoints"
    __table_args__ = {"extend_existing": True}

    epoch       = Column(Integer, primary_key=True)
    block_hash  = Column(String(128), nullable=False)
    height      = Column(Integer, nullable=False)
    votes       = Column(JSON, default=list)
    finalized   = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
