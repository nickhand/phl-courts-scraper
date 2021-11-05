"""Scrape data from the PA Unified Judicial System portal."""

import random
import time
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger

# Selenium imports
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from tryagain import retries

# Webdriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from .schema import PortalResults

__all__ = ["UJSPortalScraper"]

# The URL of the portal
PORTAL_URL = "https://ujsportal.pacourts.us/CaseSearch"


def get_webdriver(browser, debug=False):

    # Google chrome
    if browser == "chrome":
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        if not debug:
            options.add_argument("--headless")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

    # Firefox
    elif browser == "firefox":
        options = webdriver.FirefoxOptions()
        if not debug:
            options.add_argument("--headless")

        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
    else:
        raise ValueError("Unknown browser type, should be 'chrome' or 'firefox'")

    return driver


@dataclass
class UJSPortalScraper:
    """Scrape the UJS courts portal by incident number.

    Parameters
    ----------
    browser :
        either 'firefox' or 'chrome'
    debug :
        If debug mode, do not use headless driver
    sleep :
        seconds to sleep between requests
    log_freq :
        log to screen ever N requests
    """

    browser: str = "chrome"
    debug: bool = False
    log_freq: int = 50
    min_sleep: int = 30
    max_sleep: int = 120
    sleep: int = 7

    def _init(self):
        """Initialization function."""

        # Get the driver
        self.driver = get_webdriver(self.browser, debug=self.debug)

        # Navigate to the portal URL
        self.driver.get(PORTAL_URL)

        # select the search by dropdown element
        SEARCH_BY_DROPDOWN = "SearchBy-Control"
        input_searchtype = Select(
            self.driver.find_element(By.CSS_SELECTOR, f"#{SEARCH_BY_DROPDOWN} > select")
        )

        # Search by police incident
        input_searchtype.select_by_visible_text("Incident Number")

    def scrape_incident_data(self, incident_numbers):
        """Scrape the courts portal for the data associated with the input incident numbers."""

        # Initialize if we need to
        if not hasattr(self, "driver"):
            self._init()

        # Log the number
        N = len(incident_numbers)
        logger.info(f"Scraping info for {N} incidents")

        # Save new results here
        results = []

        def cleanup():
            self.driver.close()
            logger.info("Retrying...")

        @retries(
            max_attempts=15,
            cleanup_hook=cleanup,
            pre_retry_hook=self._init,
            wait=lambda n: min(
                self.min_sleep + 2 ** n + random.random(), self.max_sleep
            ),
        )
        def _call(i):

            if i % self.log_freq == 0:
                logger.debug(i)
            dc_key = str(incident_numbers[i])

            # Some DC keys for OIS are shorter
            if len(dc_key) in [10, 12]:

                # Make sure the length is 10
                if len(dc_key) == 12:
                    dc_key = dc_key[2:]

                # Scrape!
                scraping_result = self(dc_key)

                # Get the list of results
                scraping_result = scraping_result.to_dict()["data"]

                # Save results
                results.append(scraping_result)  # Could be empty list

                # Sleep!
                time.sleep(self.sleep)

        # Loop over shootings and scrape
        try:
            for i in range(N):
                _call(i)
        except:
            logger.exception(
                f"Exception raised; i = {i} & last incident number = {incident_numbers[i]}"
            )
        finally:
            logger.debug(f"Done scraping: {i+1} DC keys scraped")

        return results

    def __call__(self, dc_number: str) -> Optional[PortalResults]:
        """
        Given an input DC number for a police incident, return
        the relevant details from the courts portal.

        Parameters
        ----------
        dc_number
            the unique identifier for the police incident

        Returns
        -------
        results
            A PortalResults holding details for each unique
            docket number
        """
        # Initialize if we need to
        if not hasattr(self, "driver"):
            self._init()

        # Get the input element for the DC number
        INPUT_DC_NUMBER = "IncidentNumber-Control"
        input_dc_number = self.driver.find_element(
            By.CSS_SELECTOR, f"#{INPUT_DC_NUMBER} > input"
        )

        # Clear and add our desired DC number
        input_dc_number.clear()
        input_dc_number.send_keys(str(dc_number))

        # Submit the search
        SEARCH_BUTTON = "btnSearch"
        self.driver.find_element(By.CSS_SELECTOR, f"#{SEARCH_BUTTON}").click()

        # Results / no results elements
        RESULTS_CONTAINER = "caseSearchResultGrid"

        # Wait explicitly until search results load
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"#{RESULTS_CONTAINER}")
            ),
        )

        # Initialize the soup
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # if results succeeded, parse them
        out = None
        try:

            # Table holding the search results
            results_table = soup.select_one(f"#{RESULTS_CONTAINER}")

            # The rows of the search page
            results_rows = results_table.select("tbody > tr")

            # result fields
            fields = [
                "docket_number",
                "court_type",
                "short_caption",
                "case_status",
                "filing_date",
                "party",
                "date_of_birth",
                "county",
                "court_office",
                "otn",
                "lotn",
                "dc_number",
            ]

            # extract data for each row, including links
            data = []
            for row in results_rows:

                # the data displayed in the row itself
                texts = [
                    td.text
                    for td in row.select("td")
                    if "display-none" not in td.attrs.get("class", [])
                ]

                # No text? Skip!
                if not len(texts):
                    continue

                # Make sure we check the length
                # Last td cell is unnecessary — it holds the urls (added below)
                assert len(texts) == len(fields) + 1
                X = dict(zip(fields, texts[:-1]))

                # the urls to the court summary and docket sheet
                urls = [a.attrs["href"] for a in row.select("a")]
                X["court_summary_url"] = urls[-1]
                X["docket_sheet_url"] = urls[-2]

                # Save it
                data.append(X)

            # Return a Portal Results
            out = PortalResults.from_dict({"data": data})

        except NoSuchElementException:
            pass

        return out
