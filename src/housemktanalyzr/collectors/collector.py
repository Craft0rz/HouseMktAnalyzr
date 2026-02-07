"""Data collection orchestrator.

This module provides the DataCollector class which orchestrates data collection
from multiple property data sources. It handles source prioritization, fallback
on failure, caching, and unified access to property listings.
"""

import logging
import time
from typing import Any, Optional

from ..models.property import PropertyListing
from .base import DataSource, DataSourceError
from .centris import CentrisScraper

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL support."""

    def __init__(self, data: Any, ttl_seconds: int = 300):
        self.data = data
        self.created_at = time.time()
        self.ttl = ttl_seconds

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl


class DataCollector:
    """Orchestrates property data collection from multiple sources.

    DataCollector manages multiple data sources, tries them in priority order,
    and falls back to alternative sources on failure. It provides a unified
    interface for fetching property listings regardless of the underlying source.

    Features:
        - Source priority ordering (lower priority number = higher priority)
        - Automatic fallback on source failure
        - In-memory caching with TTL
        - Source availability checking
        - Logging of which source was used

    Example:
        # Auto-discover available sources
        collector = DataCollector()

        # Or explicitly provide sources
        collector = DataCollector(sources=[CentrisScraper()])

        # Fetch listings
        listings = await collector.fetch_listings(
            region="montreal",
            property_types=["DUPLEX", "TRIPLEX"],
            limit=50
        )

        # Check available sources
        print(collector.get_available_sources())  # ["centris"]
    """

    # Default cache TTL in seconds (5 minutes)
    DEFAULT_CACHE_TTL = 300

    def __init__(
        self,
        sources: Optional[list[DataSource]] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        auto_discover: bool = True,
    ):
        """Initialize the DataCollector.

        Args:
            sources: List of DataSource instances to use. If None and
                     auto_discover is True, will auto-discover available sources.
            cache_ttl: Cache time-to-live in seconds (default 300).
            auto_discover: If True and sources is None, auto-discover sources.
        """
        self._sources: list[DataSource] = []
        self._cache: dict[str, CacheEntry] = {}
        self.cache_ttl = cache_ttl

        if sources:
            for source in sources:
                self.add_source(source)
        elif auto_discover:
            self._auto_discover_sources()

    def _auto_discover_sources(self) -> None:
        """Auto-discover and register available data sources.

        This method instantiates all known data source classes and adds
        those that are available (configured properly) to the source list.
        """
        # List of source classes to try
        source_classes = [
            CentrisScraper,
            # Future sources:
            # HouskiAPI,
            # RepliersAPI,
        ]

        for source_class in source_classes:
            try:
                source = source_class()
                if source.is_available():
                    self.add_source(source)
                    logger.info(f"Auto-discovered source: {source.name}")
            except Exception as e:
                logger.debug(f"Could not initialize {source_class.__name__}: {e}")

    def add_source(self, source: DataSource) -> None:
        """Register a new data source.

        Args:
            source: DataSource instance to add

        Note:
            Sources are automatically sorted by priority after adding.
        """
        if source not in self._sources:
            self._sources.append(source)
            # Sort by priority (lower = higher priority)
            self._sources.sort(key=lambda s: s.priority)
            logger.debug(f"Added source: {source.name} (priority {source.priority})")

    def remove_source(self, name: str) -> bool:
        """Remove a data source by name.

        Args:
            name: Name of the source to remove

        Returns:
            True if source was removed, False if not found
        """
        for i, source in enumerate(self._sources):
            if source.name == name:
                self._sources.pop(i)
                logger.debug(f"Removed source: {name}")
                return True
        return False

    def get_available_sources(self) -> list[str]:
        """Get names of all available/configured data sources.

        Returns:
            List of source names in priority order
        """
        return [s.name for s in self._sources if s.is_available()]

    def get_source(self, name: str) -> Optional[DataSource]:
        """Get a specific data source by name.

        Args:
            name: Name of the source to get

        Returns:
            DataSource instance or None if not found
        """
        for source in self._sources:
            if source.name == name:
                return source
        return None

    def _get_cache_key(
        self,
        region: str,
        property_types: Optional[list[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        """Generate a cache key from search parameters."""
        types_str = ",".join(sorted(property_types)) if property_types else "all"
        return f"{region}:{types_str}:{min_price}:{max_price}:{limit}"

    def _get_cached(self, cache_key: str) -> Optional[list[PropertyListing]]:
        """Get cached results if available and not expired."""
        entry = self._cache.get(cache_key)
        if entry and not entry.is_expired():
            logger.debug(f"Cache hit: {cache_key}")
            return entry.data
        return None

    def _set_cached(self, cache_key: str, data: list[PropertyListing]) -> None:
        """Store results in cache."""
        self._cache[cache_key] = CacheEntry(data, self.cache_ttl)
        logger.debug(f"Cached: {cache_key}")

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        logger.debug("Cache cleared")

    async def fetch_listings(
        self,
        region: str = "montreal",
        property_types: Optional[list[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: Optional[int] = None,
        use_cache: bool = True,
        preferred_source: Optional[str] = None,
    ) -> list[PropertyListing]:
        """Fetch property listings from the highest-priority available source.

        Tries sources in priority order, falling back to the next source
        if one fails. Results are cached to reduce redundant requests.

        Args:
            region: Geographic region to search (default "montreal")
            property_types: Filter by property types (e.g., ["DUPLEX", "TRIPLEX"])
            min_price: Minimum listing price in CAD
            max_price: Maximum listing price in CAD
            limit: Maximum number of listings to return
            use_cache: Whether to use cached results (default True)
            preferred_source: Name of preferred source to try first

        Returns:
            List of PropertyListing objects

        Raises:
            DataSourceError: If all sources fail
        """
        # Check cache first
        cache_key = self._get_cache_key(
            region, property_types, min_price, max_price, limit
        )
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        # Build source list (preferred first, then by priority)
        sources_to_try = list(self._sources)
        if preferred_source:
            source = self.get_source(preferred_source)
            if source:
                sources_to_try.remove(source)
                sources_to_try.insert(0, source)

        # Filter to available sources
        sources_to_try = [s for s in sources_to_try if s.is_available()]

        if not sources_to_try:
            raise DataSourceError("collector", "No data sources available")

        errors = []
        for source in sources_to_try:
            try:
                logger.info(f"Fetching from source: {source.name}")
                listings = await source.fetch_listings(
                    region=region,
                    property_types=property_types,
                    min_price=min_price,
                    max_price=max_price,
                    limit=limit,
                )

                # Cache successful results
                if use_cache and listings:
                    self._set_cached(cache_key, listings)

                logger.info(f"Fetched {len(listings)} listings from {source.name}")
                return listings

            except DataSourceError as e:
                logger.warning(f"Source {source.name} failed: {e}")
                errors.append(f"{source.name}: {e}")
                continue

            except Exception as e:
                logger.error(f"Unexpected error from {source.name}: {e}")
                errors.append(f"{source.name}: {e}")
                continue

        # All sources failed
        error_msg = "All sources failed: " + "; ".join(errors)
        raise DataSourceError("collector", error_msg)

    async def get_listing_details(
        self,
        listing_id: str,
        source_name: Optional[str] = None,
    ) -> Optional[PropertyListing]:
        """Get full details for a single listing.

        Args:
            listing_id: The listing ID (may include source prefix)
            source_name: Specific source to use (auto-detected if None)

        Returns:
            PropertyListing with full details, or None if not found
        """
        # Try to detect source from listing ID
        if source_name is None:
            for source in self._sources:
                if listing_id.startswith(f"{source.name}-"):
                    source_name = source.name
                    break

        # Get from specific source
        if source_name:
            source = self.get_source(source_name)
            if source:
                return await source.get_listing_details(listing_id)
            return None

        # Try all sources
        for source in self._sources:
            if source.is_available():
                try:
                    result = await source.get_listing_details(listing_id)
                    if result:
                        return result
                except Exception:
                    continue

        return None

    async def close(self) -> None:
        """Close all data sources and release resources."""
        for source in self._sources:
            if hasattr(source, "close"):
                try:
                    await source.close()
                except Exception as e:
                    logger.debug(f"Error closing {source.name}: {e}")

    async def __aenter__(self) -> "DataCollector":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
