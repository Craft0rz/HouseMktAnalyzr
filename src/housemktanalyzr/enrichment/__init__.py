"""Data enrichment modules for property analysis.

This package provides supplementary data sources to enrich property listings
with rental estimates, assessment values, and other market data.
"""

from .assessment import QuebecAssessmentData
from .cmhc import CMHCRentalData

__all__ = ["CMHCRentalData", "QuebecAssessmentData"]
