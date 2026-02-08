"""Data enrichment modules for property analysis.

This package provides supplementary data sources to enrich property listings
with rental estimates, assessment values, and other market data.
"""

from .assessment import QuebecAssessmentData
from .cmhc import CMHCRentalData
from .cmhc_client import CMHCClient
from .condition_scorer import ConditionScoreResult, score_property_condition
from .market_data import BankOfCanadaClient, Observation, RateHistory
from .rent_intel import RentForecast, RentTrend, analyze_zone_rent
from .walkscore import WalkScoreResult, enrich_with_walk_score

__all__ = [
    "BankOfCanadaClient",
    "CMHCClient",
    "CMHCRentalData",
    "ConditionScoreResult",
    "Observation",
    "QuebecAssessmentData",
    "RateHistory",
    "RentForecast",
    "RentTrend",
    "WalkScoreResult",
    "analyze_zone_rent",
    "enrich_with_walk_score",
    "score_property_condition",
]
