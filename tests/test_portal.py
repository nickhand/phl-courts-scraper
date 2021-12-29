import pytest
from phl_courts_scraper.portal.core import UJSPortalScraper
from phl_courts_scraper.portal.schema import PortalResult, PortalResults


def test_scrape_incident_number():
    """Test scraping for a successful DC number."""

    # Search by incident number
    scraper = UJSPortalScraper(search_by="Incident Number")

    # scrape
    data = scraper("1725088232")
    assert len(data) == 2
    assert isinstance(data, PortalResults)
    for result in data:
        assert isinstance(result, PortalResult)


def test_scrape_docket_number():
    """Test scraping for a successful docket number."""

    # Search by docket number
    scraper = UJSPortalScraper(search_by="Docket Number")

    # scrape
    data = scraper("MC-51-CR-0023037-2021")
    assert len(data) == 1
    assert isinstance(data, PortalResults)
    for result in data:
        assert isinstance(result, PortalResult)


def test_scrape_failure():
    """Test scraping failure."""

    # Search by incident number
    scraper = UJSPortalScraper(search_by="Incident Number")

    # Fail with bad dc number
    data = scraper("172508823")
    assert len(data) == 0
