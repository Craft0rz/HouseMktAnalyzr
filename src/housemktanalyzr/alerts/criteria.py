"""Alert criteria models and persistence."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ..models.property import PropertyType

logger = logging.getLogger(__name__)


class AlertCriteria(BaseModel):
    """Saved search criteria for property alerts.

    Stores user-defined investment criteria that will trigger
    notifications when matching properties are found.

    Example:
        criteria = AlertCriteria(
            name="South Shore Triplexes",
            regions=["montreal-south-shore"],
            property_types=[PropertyType.TRIPLEX],
            min_price=400000,
            max_price=700000,
            min_score=60,
            min_cap_rate=5.0,
        )
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    enabled: bool = True

    # Search criteria
    regions: list[str] = Field(default_factory=list)
    property_types: list[PropertyType] = Field(default_factory=list)
    min_price: Optional[int] = None
    max_price: Optional[int] = None

    # Investment filters
    min_score: Optional[float] = None
    min_cap_rate: Optional[float] = None
    min_cash_flow: Optional[int] = None
    max_price_per_unit: Optional[int] = None
    min_yield: Optional[float] = None

    # Notification settings
    notify_email: Optional[str] = None
    notify_on_new: bool = True
    notify_on_price_drop: bool = True

    # Tracking
    last_checked: Optional[datetime] = None
    last_match_count: int = 0

    def model_post_init(self, __context) -> None:
        """Ensure updated_at is set on changes."""
        pass

    def matches_listing(self, listing, metrics) -> bool:
        """Check if a listing matches this criteria."""
        # Property type filter
        if self.property_types and listing.property_type not in self.property_types:
            return False

        # Price filters
        if self.min_price and listing.price < self.min_price:
            return False
        if self.max_price and listing.price > self.max_price:
            return False

        # Investment filters
        if self.min_score and metrics.score < self.min_score:
            return False
        if self.min_cap_rate and (metrics.cap_rate or 0) < self.min_cap_rate:
            return False
        if self.min_cash_flow and (metrics.cash_flow_monthly or 0) < self.min_cash_flow:
            return False
        if self.max_price_per_unit and metrics.price_per_unit > self.max_price_per_unit:
            return False
        if self.min_yield and metrics.gross_rental_yield < self.min_yield:
            return False

        return True


class CriteriaManager:
    """Manage saved alert criteria with JSON persistence.

    Stores criteria in a JSON file in the user's home directory.
    Supports CRUD operations and filtering by enabled status.

    Example:
        manager = CriteriaManager()
        manager.save(criteria)
        all_criteria = manager.list_all()
        enabled = manager.get_enabled()
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize manager with config path.

        Args:
            config_path: Path to JSON config file. Defaults to
                        ~/.housemktanalyzr/alerts.json
        """
        if config_path is None:
            config_path = Path.home() / ".housemktanalyzr" / "alerts.json"
        self.config_path = Path(config_path)
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all_data(self) -> dict[str, dict]:
        """Load all criteria from JSON file."""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                return data.get("criteria", {})
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load criteria: {e}")
            return {}

    def _save_all_data(self, criteria_dict: dict[str, dict]) -> None:
        """Save all criteria to JSON file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump({"criteria": criteria_dict}, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save criteria: {e}")
            raise

    def save(self, criteria: AlertCriteria) -> None:
        """Save or update alert criteria.

        Args:
            criteria: AlertCriteria to save
        """
        all_data = self._load_all_data()

        # Update timestamp
        criteria.updated_at = datetime.now()

        # Convert to dict for storage
        criteria_dict = criteria.model_dump(mode="json")
        all_data[criteria.id] = criteria_dict

        self._save_all_data(all_data)
        logger.info(f"Saved criteria: {criteria.name} ({criteria.id})")

    def load(self, criteria_id: str) -> Optional[AlertCriteria]:
        """Load criteria by ID.

        Args:
            criteria_id: UUID of criteria to load

        Returns:
            AlertCriteria if found, None otherwise
        """
        all_data = self._load_all_data()

        if criteria_id not in all_data:
            return None

        try:
            return AlertCriteria.model_validate(all_data[criteria_id])
        except Exception as e:
            logger.warning(f"Failed to parse criteria {criteria_id}: {e}")
            return None

    def list_all(self) -> list[AlertCriteria]:
        """List all saved criteria.

        Returns:
            List of all AlertCriteria, sorted by name
        """
        all_data = self._load_all_data()
        criteria_list = []

        for criteria_dict in all_data.values():
            try:
                criteria = AlertCriteria.model_validate(criteria_dict)
                criteria_list.append(criteria)
            except Exception as e:
                logger.warning(f"Failed to parse criteria: {e}")

        return sorted(criteria_list, key=lambda c: c.name)

    def delete(self, criteria_id: str) -> bool:
        """Delete criteria by ID.

        Args:
            criteria_id: UUID of criteria to delete

        Returns:
            True if deleted, False if not found
        """
        all_data = self._load_all_data()

        if criteria_id not in all_data:
            return False

        del all_data[criteria_id]
        self._save_all_data(all_data)
        logger.info(f"Deleted criteria: {criteria_id}")
        return True

    def get_enabled(self) -> list[AlertCriteria]:
        """Get all enabled criteria for alert checking.

        Returns:
            List of enabled AlertCriteria
        """
        return [c for c in self.list_all() if c.enabled]

    def update_last_checked(
        self, criteria_id: str, match_count: int = 0
    ) -> None:
        """Update last checked timestamp for criteria.

        Args:
            criteria_id: UUID of criteria
            match_count: Number of matches found
        """
        criteria = self.load(criteria_id)
        if criteria:
            criteria.last_checked = datetime.now()
            criteria.last_match_count = match_count
            self.save(criteria)
