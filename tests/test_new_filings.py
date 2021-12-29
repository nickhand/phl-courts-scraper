import pytest
from phl_courts_scraper.new_filings.core import NewFilingsScraper
from phl_courts_scraper.new_filings.schema import (
    NewCriminalFiling,
    NewCriminalFilings,
)


@pytest.fixture
def scraper():
    """Return a `NewFilingsScraper` to use in multiple tests."""
    return NewFilingsScraper()


def test_scrape_successful(scraper):
    """Test scraping"""

    # scrape
    data = scraper()
    assert isinstance(data, NewCriminalFilings)
    for result in data:
        assert isinstance(result, NewCriminalFiling)
