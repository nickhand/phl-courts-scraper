import pytest
from phl_courts_scraper.scrape import IncidentNumberScraper
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager


@pytest.fixture
def scraper():
    """Return a `IncidentNumberScraper` to use in multiple tests."""

    # Initialize the driver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)

    # Return the scraper
    return IncidentNumberScraper(driver)


def test_scrape_successful(scraper):
    """Test scraping for a successful DC number."""

    # scrape
    data = scraper.scrape("1725088232")
    assert len(data) == 2


def test_scrape_failure(scraper):
    """Test scraping failure."""

    # Fail with bad dc number
    data = scraper.scrape("17")
    assert data is None
