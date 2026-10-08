"""Domain model (no Qt)."""

from doex.core.campaign import Campaign
from doex.core.schema import (
    CampaignSchema,
    ColumnMapping,
    Factor,
    FactorType,
    Response,
    ResponseGoal,
    SuggestAlgorithm,
    SuggestMode,
    SuggestSettings,
)

__all__ = [
    "Campaign",
    "CampaignSchema",
    "ColumnMapping",
    "Factor",
    "FactorType",
    "Response",
    "ResponseGoal",
    "SuggestAlgorithm",
    "SuggestMode",
    "SuggestSettings",
]
