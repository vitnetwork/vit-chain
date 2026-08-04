"""
tests/test_math.py — Deterministic math helpers used by the consensus engine.
"""
import pytest
from decimal import Decimal


class TestCryptoHelpers:
    def test_chain_imports(self):
        """Core chain modules import without error."""
        import chain.config
        import chain.models
        assert True

    def test_config_genesis_timestamp(self):
        from chain.config import settings
        # Genesis timestamp should be 2025-01-01 UTC
        assert settings.GENESIS_TIMESTAMP == 1735689600

    def test_block_reward_positive(self):
        from chain.config import settings
        assert float(settings.BLOCK_REWARD_VIT) > 0

    def test_initial_supply_positive(self):
        from chain.config import settings
        assert settings.INITIAL_SUPPLY_VIT > 0


class TestModelDefinitions:
    def test_chain_block_columns(self):
        from chain.models import ChainBlock
        cols = {c.name for c in ChainBlock.__table__.columns}
        assert "height" in cols
        assert "block_hash" in cols
        assert "validator_id" in cols
        assert "storage_proofs" in cols

    def test_validator_columns(self):
        from chain.models import Validator
        cols = {c.name for c in Validator.__table__.columns}
        assert "address" in cols
        assert "stake" in cols
        assert "status" in cols

    def test_slash_record_columns(self):
        from chain.models import SlashRecord
        cols = {c.name for c in SlashRecord.__table__.columns}
        assert "validator_address" in cols
        assert "reason" in cols
        assert "slash_amount" in cols
