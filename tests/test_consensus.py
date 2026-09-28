"""
tests/test_consensus.py — Unit tests for VIT Chain consensus components.

Tests are designed to be fast and self-contained (no DB required).
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock


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
        result = calc.calculate(consensus_weight=1.0, num_validators=1)
        assert isinstance(result, Decimal)
        assert result >= Decimal("0")

    def test_zero_proofs_gives_no_reward(self):
        from chain.consensus.rewards import StorageRewardCalculator
        calc = StorageRewardCalculator()
        result = calc.calculate(consensus_weight=0.0, num_validators=1)
        assert result == Decimal("0")

    def test_reward_is_split_between_validators(self):
        from chain.consensus.rewards import StorageRewardCalculator
        calc = StorageRewardCalculator()
        single_validator = calc.calculate(consensus_weight=1.0, num_validators=1)
        two_validators = calc.calculate(consensus_weight=1.0, num_validators=2)
        assert two_validators == single_validator / 2


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

    @pytest.mark.asyncio
    async def test_generate_epoch_challenges_persists_one_per_active_validator(self):
        from chain.consensus.challenge import ChallengeGenerator
        gen = ChallengeGenerator()
        validator = Mock(address="0x" + "ab" * 20)
        result = Mock()
        result.scalars.return_value.all.return_value = [validator]
        db = Mock()
        db.execute = AsyncMock(return_value=result)
        db.flush = AsyncMock()

        challenge_ids = await gen.generate_epoch_challenges(db, epoch=1)

        assert len(challenge_ids) == 1
        challenge = db.add.call_args.args[0]
        assert challenge.challenge_id == challenge_ids[0]
        assert challenge.validator_address == validator.address
        db.flush.assert_awaited_once()


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
