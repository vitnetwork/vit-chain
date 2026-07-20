"""
chain/consensus/rewards.py — StorageRewardCalculator.
"""
from __future__ import annotations
from decimal import Decimal
from chain.config import settings


class StorageRewardCalculator:

    def calculate(self, consensus_weight: float, num_validators: int) -> Decimal:
        """
        Block reward scales with consensus weight and splits among validators.
        Base reward per block = BLOCK_REWARD_VIT.
        """
        base = Decimal(str(settings.BLOCK_REWARD_VIT))
        weight = Decimal(str(max(0.0, min(1.0, consensus_weight))))
        if num_validators < 1:
            num_validators = 1
        per_validator = (base * weight) / Decimal(str(num_validators))
        return per_validator.quantize(Decimal("0.000001"))
