"""Alert checker for finding matching properties."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..analysis import PropertyRanker
from ..collectors.centris import CentrisScraper
from ..models.property import InvestmentMetrics, PropertyListing
from .criteria import AlertCriteria, CriteriaManager

logger = logging.getLogger(__name__)


class AlertChecker:
    """Check for properties matching alert criteria.

    Fetches properties from Centris, analyzes them, and identifies
    which ones match saved alert criteria. Tracks seen listings to
    avoid duplicate notifications.

    Example:
        checker = AlertChecker()
        results = await checker.check_all()
        for criteria_id, matches in results.items():
            print(f"{criteria_id}: {len(matches)} matches")
    """

    def __init__(
        self,
        criteria_manager: Optional[CriteriaManager] = None,
        seen_file: Optional[Path] = None,
    ):
        """Initialize checker.

        Args:
            criteria_manager: CriteriaManager instance
            seen_file: Path to store seen listing IDs
        """
        self.scraper = CentrisScraper()
        self.ranker = PropertyRanker()
        self.criteria_mgr = criteria_manager or CriteriaManager()

        if seen_file is None:
            seen_file = Path.home() / ".housemktanalyzr" / "seen_listings.json"
        self.seen_file = seen_file
        self._ensure_seen_file()

    def _ensure_seen_file(self) -> None:
        """Create seen file directory if needed."""
        self.seen_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_seen(self, criteria_id: str) -> set[str]:
        """Load seen listing IDs for a criteria."""
        if not self.seen_file.exists():
            return set()

        try:
            with open(self.seen_file, "r") as f:
                data = json.load(f)
                return set(data.get(criteria_id, []))
        except (json.JSONDecodeError, IOError):
            return set()

    def _save_seen(self, criteria_id: str, listing_ids: set[str]) -> None:
        """Save seen listing IDs for a criteria."""
        data = {}
        if self.seen_file.exists():
            try:
                with open(self.seen_file, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        data[criteria_id] = list(listing_ids)

        with open(self.seen_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_criteria_hash(self, criteria: AlertCriteria) -> str:
        """Get unique hash for criteria search parameters."""
        key_parts = [
            ",".join(sorted(criteria.regions)),
            ",".join(sorted(t.value for t in criteria.property_types)),
            str(criteria.min_price or 0),
            str(criteria.max_price or 0),
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()[:8]

    async def check_criteria(
        self,
        criteria: AlertCriteria,
        only_new: bool = True,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Find properties matching criteria.

        Args:
            criteria: AlertCriteria to check
            only_new: If True, filter to only new listings

        Returns:
            List of matching (PropertyListing, InvestmentMetrics) tuples
        """
        all_matches = []

        for region in criteria.regions:
            # Build search URL
            url = f"https://www.centris.ca/en/plexes~for-sale~{region}"

            logger.info(f"Fetching properties from {region}...")

            try:
                listings = await self.scraper.fetch_all_listings(
                    url,
                    min_price=criteria.min_price,
                    max_price=criteria.max_price,
                    max_pages=10,
                )

                if not listings:
                    continue

                # Analyze all listings
                analyzed = self.ranker.analyze_batch(listings)

                # Filter by criteria
                for listing, metrics in analyzed:
                    if criteria.matches_listing(listing, metrics):
                        all_matches.append((listing, metrics))

            except Exception as e:
                logger.error(f"Error checking {region}: {e}")

        # Filter to new listings only
        if only_new and all_matches:
            seen = self._load_seen(criteria.id)
            new_matches = [
                (l, m) for l, m in all_matches
                if l.id not in seen
            ]

            # Update seen listings
            new_ids = {l.id for l, _ in all_matches}
            self._save_seen(criteria.id, seen | new_ids)

            # Update criteria tracking
            self.criteria_mgr.update_last_checked(criteria.id, len(new_matches))

            return new_matches

        return all_matches

    async def check_all(
        self,
        only_new: bool = True,
    ) -> dict[str, list[tuple[PropertyListing, InvestmentMetrics]]]:
        """Check all enabled criteria.

        Args:
            only_new: If True, filter to only new listings

        Returns:
            Dict mapping criteria ID to list of matches
        """
        results = {}
        enabled_criteria = self.criteria_mgr.get_enabled()

        if not enabled_criteria:
            logger.info("No enabled criteria to check")
            return results

        logger.info(f"Checking {len(enabled_criteria)} enabled criteria...")

        for criteria in enabled_criteria:
            logger.info(f"Checking: {criteria.name}")
            matches = await self.check_criteria(criteria, only_new=only_new)
            results[criteria.id] = matches

            if matches:
                logger.info(f"  Found {len(matches)} matches")
            else:
                logger.info(f"  No new matches")

        return results

    def get_new_listings(
        self,
        current: list[PropertyListing],
        criteria_id: str,
    ) -> list[PropertyListing]:
        """Filter to only new listings not seen before.

        Args:
            current: List of current listings
            criteria_id: Criteria ID for tracking

        Returns:
            List of new listings only
        """
        seen = self._load_seen(criteria_id)
        return [l for l in current if l.id not in seen]

    def mark_as_seen(
        self,
        listings: list[PropertyListing],
        criteria_id: str,
    ) -> None:
        """Mark listings as seen for a criteria.

        Args:
            listings: Listings to mark as seen
            criteria_id: Criteria ID
        """
        seen = self._load_seen(criteria_id)
        new_ids = {l.id for l in listings}
        self._save_seen(criteria_id, seen | new_ids)
