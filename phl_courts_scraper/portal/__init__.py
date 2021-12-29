"""Parse the UJS court portal."""

from .core import UJSPortalScraper  # noqa: F401
from .schema import PortalResult, PortalResults  # noqa: F401

__all__ = ["UJSPortalScraper", "PortalResult", "PortalResults"]
