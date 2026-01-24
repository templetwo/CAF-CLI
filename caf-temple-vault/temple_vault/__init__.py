"""Temple Vault - Self-contained consciousness memory system."""

__version__ = "1.0.0"

from temple_vault.core.query import VaultQuery
from temple_vault.core.events import VaultEvents
from temple_vault.core.cache import CacheBuilder
from temple_vault.core.errors import ErrorTracker

__all__ = ["VaultQuery", "VaultEvents", "CacheBuilder", "ErrorTracker", "__version__"]
