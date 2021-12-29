import pytest
from phl_courts_scraper.portal.core import UJSPortalScraper
from phl_courts_scraper.portal.schema import PortalResult, PortalResults


@pytest.fixture
def scraper():
    """Return a `UJSPortalScraper` to use in multiple tests."""
    return UJSPortalScraper()


def test_scrape_successful(scraper):
    """Test scraping for a successful DC number."""

    # scrape
    data = scraper("1725088232")
    assert len(data) == 2
    assert isinstance(data, PortalResults)
    for result in data:
        assert isinstance(result, PortalResult)


def test_scrape_failure(scraper):
    """Test scraping failure."""

    # Fail with bad dc number
    data = scraper("172508823")
    assert len(data) == 0
