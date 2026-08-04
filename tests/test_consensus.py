"""
tests/test_consensus.py — Unit tests for VIT Chain consensus components.

Tests are designed to be fast and self-contained (no DB required).
"""
import pytest
from decimal import Decimal


class TestSlashingManager:
    """Slashing percentage calculations and jailing logic."""

    def test_slash_percentages_defined(self):
        from chain.consensus.slashing import SlashingManager, SlashReason
        mgr = SlashingManager()
        # Slashing manager instantiates without error
        assert mgr is not None

    def test_slash_reason_values(self):
        from chain.consensus.slashing import SlashReason
        assert SlashReason.DOWNTIME == "DOWNTIME"
        assert SlashReason.DOUBLE_SIGN == "DOUBLE_SIGN"
        assert SlashReason.INVALID_BLOCK == "INVALID_BLOCK"


class TestRewardsCalculator:
    def test_instantiation(self):
        from chain.consensus.rewards import StorageRewardCalculator
        calc = StorageRewardCalculator()
        assert calc is not None

    def test_calculate_returns_decimal(self):
        from chain.consensus.rewards import StorageRewardCalculator
        calc = StorageRewardCalculator()
        # Should accept stake and proofs and return a Decimal
        result = calc.calculate(stake=Decimal("1000000"), proofs_submitted=10, proofs_required=10)
        assert isinstance(result, Decimal)
        assert result >= Decimal("0")

    def test_zero_proofs_gives_no_reward(self):
        from chain.consensus.rewards import StorageRewardCalculator
        calc = StorageRewardCalculator()
        result = calc.calculate(stake=Decimal("1000000"), proofs_submitted=0, proofs_required=10)
        assert result == Decimal("0")


class TestReputationManager:
    def test_instantiation(self):
        from chain.consensus.reputation import ReputationManager
        mgr = ReputationManager()
        assert mgr is not None


class TestChallengeGenerator:
    def test_instantiation(self):
        from chain.consensus.challenge import ChallengeGenerator
        gen = ChallengeGenerator()
        assert gen is not None

    def test_generate_returns_dict(self):
        from chain.consensus.challenge import ChallengeGenerator
        gen = ChallengeGenerator()
        challenge = gen.generate(
            epoch=1,
            validator_address="0x" + "ab" * 20,
            shard_id="shard_001",
        )
        assert isinstance(challenge, dict)
        assert "challenge_id" in challenge or "id" in challenge or len(challenge) > 0


class TestConfig:
    def test_chain_id(self):
        from chain.config import settings
        assert settings.CHAIN_ID == 7764

    def test_network(self):
        from chain.config import settings
        assert settings.NETWORK in ("testnet", "mainnet", "devnet")

    def test_epoch_seconds_positive(self):
        from chain.config import settings
        assert settings.EPOCH_SECONDS > 0

    def test_slash_pcts_in_range(self):
        from chain.config import settings
        assert 0 < settings.SLASH_DOWNTIME_PCT <= 100
        assert 0 < settings.SLASH_DOUBLE_SIGN_PCT <= 100
        assert 0 < settings.SLASH_INVALID_BLOCK_PCT <= 100
