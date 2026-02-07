"""Storage modules for property data persistence.

This package provides caching and storage capabilities for property listings
to avoid redundant API calls and enable offline analysis.
"""

from .cache import PropertyCache

__all__ = ["PropertyCache"]
