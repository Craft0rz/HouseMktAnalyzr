"""Property data collection framework.

This module provides a unified interface for collecting property data from
multiple sources (Centris, Houski, etc.) through a plugin architecture.

Main Components:
    - DataSource: Abstract base class for all data sources
    - DataCollector: Orchestrator that manages multiple sources
    - CentrisScraper: Web scraper for Centris.ca listings

Example usage:
    from housemktanalyzr.collectors import DataCollector, CentrisScraper

    # Auto-discover available sources
    collector = DataCollector()
    listings = await collector.fetch_listings(region="montreal")

    # Or use a specific source
    scraper = CentrisScraper()
    listings = await scraper.fetch_listings(region="montreal", limit=50)
"""

from .base import CaptchaError, DataSource, DataSourceError, RateLimitError
from .centris import CentrisScraper
from .collector import DataCollector

__all__ = [
    "DataSource",
    "DataSourceError",
    "RateLimitError",
    "CaptchaError",
    "CentrisScraper",
    "DataCollector",
]
