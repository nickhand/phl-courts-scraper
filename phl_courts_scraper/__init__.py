"""Init module for phl_courts_scraper."""


try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version  # type: ignore


__version__ = version(__package__)
