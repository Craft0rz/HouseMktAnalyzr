"""Configuration system for HouseMktAnalyzr.

Uses pydantic-settings to load configuration from environment variables
and .env files with sensible defaults for Montreal real estate analysis.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    Environment variables are prefixed with HOUSEMKT_ (e.g., HOUSEMKT_REGION).
    """

    model_config = SettingsConfigDict(
        env_prefix="HOUSEMKT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Target market settings
    region: str = Field(
        default="montreal",
        description="Target market region for analysis",
    )
    min_price: int = Field(
        default=200000,
        ge=0,
        description="Minimum property price in CAD",
    )
    max_price: int = Field(
        default=2000000,
        ge=0,
        description="Maximum property price in CAD",
    )
    property_types: list[str] = Field(
        default=["DUPLEX", "TRIPLEX", "QUADPLEX", "MULTIPLEX"],
        description="Property types to analyze",
    )
    min_units: int = Field(
        default=2,
        ge=1,
        description="Minimum number of units (focus on income properties)",
    )

    # Investment criteria
    target_yield: float = Field(
        default=5.0,
        ge=0,
        description="Minimum gross rental yield percentage",
    )
    target_cap_rate: float = Field(
        default=4.0,
        ge=0,
        description="Minimum cap rate percentage",
    )

    # API keys (loaded from environment)
    centris_api_key: str | None = Field(
        default=None,
        description="API key for Centris data access",
    )
    realtor_api_key: str | None = Field(
        default=None,
        description="API key for Realtor.ca data access",
    )

    # Data paths
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for storing property data",
    )
    cache_dir: Path = Field(
        default=Path(".cache"),
        description="Directory for caching API responses",
    )


# Singleton instance for easy import
config = Settings()
