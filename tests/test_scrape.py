import pytest
from selenium import webdriver
import chromedriver_binary

from phl_courts_scraper.scrape import (
    initialize_incident_scrape,
    scrape_data_by_incident,
)


@pytest.fixture
def driver():

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    return webdriver.Chrome(options=options)


def test_scrape_successful(driver):

    # initialize the scrape
    initialize_incident_scrape(driver)

    # scrape
    data = scrape_data_by_incident(driver, "1725088232")
    assert len(data) == 2


def test_scrape_failure(driver):

    # initialize the scrape
    initialize_incident_scrape(driver)

    # scrape
    data = scrape_data_by_incident(driver, "17")
    assert data is None
