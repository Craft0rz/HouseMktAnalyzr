"""Abstract base class for property data sources.

This module defines the DataSource abstract base class that all property data
sources must implement. The plugin architecture allows for multiple data sources
(Centris, Houski, Repliers, etc.) to be used interchangeably through a unified
interface.

Example usage:
    class MyDataSource(DataSource):
        name = "my_source"
        priority = 10

        async def fetch_listings(self, region, **kwargs):
            # Implementation here
            pass

        async def get_listing_details(self, listing_id):
            # Implementation here
            pass

        def is_available(self):
            return True
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..models.property import PropertyListing


class DataSource(ABC):
    """Abstract base class for property data sources.

    All data sources (scrapers, APIs, etc.) must implement this interface
    to be compatible with the DataCollector orchestrator.

    Attributes:
        name: Unique identifier for this data source (e.g., "centris", "houski")
        priority: Lower values = higher priority. Used to determine which source
                  to try first when multiple sources are available.

    The plugin architecture works as follows:
    1. Each data source implements this abstract class
    2. Sources register themselves with the DataCollector
    3. DataCollector queries sources in priority order
    4. If a source fails, the collector falls back to the next available source
    """

    name: str  # e.g., "centris", "houski", "repliers"
    priority: int  # lower = higher priority (0 = highest)

    @abstractmethod
    async def fetch_listings(
        self,
        region: str,
        property_types: Optional[list[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[PropertyListing]:
        """Fetch property listings matching the given criteria.

        Args:
            region: Geographic region to search (e.g., "montreal", "laval")
            property_types: Filter by property types (e.g., ["DUPLEX", "TRIPLEX"])
            min_price: Minimum listing price in CAD
            max_price: Maximum listing price in CAD
            limit: Maximum number of listings to return

        Returns:
            List of PropertyListing objects matching the criteria

        Raises:
            DataSourceError: If the source is unavailable or request fails
        """
        pass

    @abstractmethod
    async def get_listing_details(
        self, listing_id: str
    ) -> Optional[PropertyListing]:
        """Get full details for a single listing.

        Args:
            listing_id: The unique identifier for the listing (source-specific)

        Returns:
            PropertyListing with full details, or None if not found

        Raises:
            DataSourceError: If the source is unavailable or request fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this data source is configured and available.

        This method should check:
        - Required API keys or credentials are present
        - Network connectivity to the source (optional, can be lazy)
        - Any other prerequisites for the source to function

        Returns:
            True if the source is ready to use, False otherwise
        """
        pass


class DataSourceError(Exception):
    """Base exception for data source errors.

    Attributes:
        source: Name of the data source that raised the error
        message: Error description
    """

    def __init__(self, source: str, message: str):
        self.source = source
        self.message = message
        super().__init__(f"[{source}] {message}")


class RateLimitError(DataSourceError):
    """Raised when a data source rate limit is exceeded."""

    def __init__(self, source: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f" (retry after {retry_after}s)"
        super().__init__(source, message)


class CaptchaError(DataSourceError):
    """Raised when a CAPTCHA challenge is encountered."""

    def __init__(self, source: str):
        super().__init__(source, "CAPTCHA challenge detected - cannot proceed")
