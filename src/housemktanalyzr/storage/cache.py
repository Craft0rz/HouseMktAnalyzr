"""SQLite-based property cache for persisting fetched listings.

This module provides a persistent cache for PropertyListing objects,
enabling:
- Offline analysis of previously fetched data
- Reduced API calls through TTL-based caching
- Historical tracking of listings over time
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..models.property import PropertyListing, PropertyType

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = Path.home() / ".housemktanalyzr" / "cache"

# Default TTL (24 hours)
DEFAULT_TTL_HOURS = 24


class PropertyCache:
    """SQLite-based cache for property listings.

    Stores PropertyListing objects with timestamps for TTL-based expiration.
    Supports querying by region, price range, and property type.

    Example:
        cache = PropertyCache()

        # Save listings
        cache.save_batch(listings)

        # Query cached data
        cached = cache.query(
            source="centris",
            min_price=400000,
            max_price=800000,
        )

        # Clean up expired entries
        deleted = cache.prune_expired()
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        db_name: str = "properties.db",
    ):
        """Initialize the property cache.

        Args:
            cache_dir: Directory for the cache database.
                      Defaults to ~/.housemktanalyzr/cache/
            ttl_hours: Time-to-live in hours for cached entries (default 24)
            db_name: Name of the SQLite database file
        """
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.cache_dir / db_name
        self.ttl_hours = ttl_hours

        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS properties (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    city TEXT,
                    property_type TEXT,
                    price INTEGER,
                    data JSON NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_source ON properties(source)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expires ON properties(expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_city ON properties(city)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_price ON properties(price)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_type ON properties(property_type)"
            )
            conn.commit()

    def _serialize_listing(self, listing: PropertyListing) -> str:
        """Serialize a PropertyListing to JSON."""
        data = listing.model_dump(mode="json")
        return json.dumps(data)

    def _deserialize_listing(self, data: str) -> PropertyListing:
        """Deserialize JSON to a PropertyListing."""
        parsed = json.loads(data)
        # Convert property_type string back to enum
        if "property_type" in parsed and isinstance(parsed["property_type"], str):
            parsed["property_type"] = PropertyType(parsed["property_type"])
        return PropertyListing(**parsed)

    def save(self, listing: PropertyListing) -> None:
        """Save a single listing to the cache.

        Args:
            listing: PropertyListing to cache
        """
        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO properties
                (id, source, city, property_type, price, data, fetched_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.id,
                    listing.source,
                    listing.city,
                    listing.property_type.value,
                    listing.price,
                    self._serialize_listing(listing),
                    datetime.now().isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()

    def save_batch(self, listings: list[PropertyListing]) -> int:
        """Save multiple listings to the cache.

        Args:
            listings: List of PropertyListing objects to cache

        Returns:
            Number of listings saved
        """
        if not listings:
            return 0

        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)
        now = datetime.now().isoformat()
        expires = expires_at.isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO properties
                (id, source, city, property_type, price, data, fetched_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        listing.id,
                        listing.source,
                        listing.city,
                        listing.property_type.value,
                        listing.price,
                        self._serialize_listing(listing),
                        now,
                        expires,
                    )
                    for listing in listings
                ],
            )
            conn.commit()

        logger.info(f"Cached {len(listings)} listings")
        return len(listings)

    def get(self, listing_id: str) -> Optional[PropertyListing]:
        """Get a single listing by ID.

        Args:
            listing_id: The listing ID (e.g., "centris-12345678")

        Returns:
            PropertyListing if found and not expired, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT data FROM properties
                WHERE id = ? AND expires_at > ?
                """,
                (listing_id, datetime.now().isoformat()),
            )
            row = cursor.fetchone()

        if row:
            return self._deserialize_listing(row[0])
        return None

    def query(
        self,
        source: Optional[str] = None,
        city: Optional[str] = None,
        property_type: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        include_expired: bool = False,
        limit: Optional[int] = None,
    ) -> list[PropertyListing]:
        """Query cached listings with filters.

        Args:
            source: Filter by data source (e.g., "centris")
            city: Filter by city name
            property_type: Filter by property type (e.g., "DUPLEX")
            min_price: Minimum price
            max_price: Maximum price
            include_expired: Include expired entries (default False)
            limit: Maximum number of results

        Returns:
            List of matching PropertyListing objects
        """
        conditions = []
        params = []

        if not include_expired:
            conditions.append("expires_at > ?")
            params.append(datetime.now().isoformat())

        if source:
            conditions.append("source = ?")
            params.append(source)

        if city:
            conditions.append("city LIKE ?")
            params.append(f"%{city}%")

        if property_type:
            conditions.append("property_type = ?")
            params.append(property_type)

        if min_price is not None:
            conditions.append("price >= ?")
            params.append(min_price)

        if max_price is not None:
            conditions.append("price <= ?")
            params.append(max_price)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT data FROM properties WHERE {where_clause} ORDER BY price"

        if limit:
            query += f" LIMIT {limit}"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [self._deserialize_listing(row[0]) for row in rows]

    def count(
        self,
        source: Optional[str] = None,
        include_expired: bool = False,
    ) -> int:
        """Count cached listings.

        Args:
            source: Filter by data source
            include_expired: Include expired entries

        Returns:
            Number of matching listings
        """
        conditions = []
        params = []

        if not include_expired:
            conditions.append("expires_at > ?")
            params.append(datetime.now().isoformat())

        if source:
            conditions.append("source = ?")
            params.append(source)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM properties WHERE {where_clause}",
                params,
            )
            return cursor.fetchone()[0]

    def prune_expired(self) -> int:
        """Remove expired entries from the cache.

        Returns:
            Number of entries deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM properties WHERE expires_at <= ?",
                (datetime.now().isoformat(),),
            )
            conn.commit()
            deleted = cursor.rowcount

        if deleted > 0:
            logger.info(f"Pruned {deleted} expired cache entries")
        return deleted

    def clear(self, source: Optional[str] = None) -> int:
        """Clear all or source-specific cached entries.

        Args:
            source: If specified, only clear entries from this source

        Returns:
            Number of entries deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            if source:
                cursor = conn.execute(
                    "DELETE FROM properties WHERE source = ?",
                    (source,),
                )
            else:
                cursor = conn.execute("DELETE FROM properties")
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with count, sources, date range, and storage size
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total count
            total = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]

            # Active (non-expired) count
            active = conn.execute(
                "SELECT COUNT(*) FROM properties WHERE expires_at > ?",
                (datetime.now().isoformat(),),
            ).fetchone()[0]

            # By source
            sources = dict(
                conn.execute(
                    "SELECT source, COUNT(*) FROM properties GROUP BY source"
                ).fetchall()
            )

            # Date range
            dates = conn.execute(
                "SELECT MIN(fetched_at), MAX(fetched_at) FROM properties"
            ).fetchone()

        # File size
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total_entries": total,
            "active_entries": active,
            "expired_entries": total - active,
            "by_source": sources,
            "oldest_entry": dates[0],
            "newest_entry": dates[1],
            "storage_bytes": size_bytes,
            "storage_mb": round(size_bytes / (1024 * 1024), 2),
        }
