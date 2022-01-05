"""Scrape data from the PA Unified Judicial System portal."""

import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from loguru import logger

# Selenium imports
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from tryagain import retries

from ..base import get_webdriver
from .schema import PortalResults

# The URL of the portal
PORTAL_URL = "https://ujsportal.pacourts.us/CaseSearch"


@dataclass
class UJSPortalScraper:
    """
    Scrape the UJS courts portal by incident number.

    Parameters
    ----------
    search_by: str
        The search by field, either 'Incident Number' or 'Docket Number'.
    browser: str
        The browser to use; either 'firefox' or 'chrome'
    debug: bool
        Whether to use the headless version of Chrome
    log_freq: int, optional
        How often to log progress
    min_sleep: float, optional
        Minimum sleep time
    max_sleep: float, optional
        Maximum sleep time
    sleep: float, optional
        Sleep time between calls
    errors: str, optional
        How to handle scraping errors
    """

    search_by: str = "Incident Number"
    browser: str = "chrome"
    debug: bool = False
    log_freq: int = 50
    min_sleep: int = 30
    max_sleep: int = 120
    sleep: int = 7
    errors: str = "raise"

    def _init(self) -> None:
        """Initialize the web driver."""
        # Check the search by field
        assert self.search_by in ["Incident Number", "Docket Number"]

        # Get the driver
        logger.info("Initializing web driver")
        self.driver = get_webdriver(self.browser, debug=self.debug)

        # Navigate to the portal URL
        logger.info("Getting portal URL")
        self.driver.get(PORTAL_URL)

        # select the search by dropdown element
        logger.info("Selecting search by dropdown")
        SEARCH_BY_DROPDOWN = "SearchBy-Control"
        input_searchtype = Select(
            self.driver.find_element(
                By.CSS_SELECTOR, f"#{SEARCH_BY_DROPDOWN} > select"
            )
        )

        # Set the search by field
        logger.info("Setting search by field")
        input_searchtype.select_by_visible_text(self.search_by)

    def scrape_portal_data(
        self, input_values: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Scrape portal data for a list of input values.

        Parameters
        ----------
        input_values: List[str]
            The list of input values to scrape

        Returns
        -------
        results: List[PortalResults]
            The results of the scraper, or None if the scraper failed

        Raises
        ------
        Exception
            If the scraping fails
        """
        # Initialize if we need to
        if not hasattr(self, "driver"):
            self._init()

        # Log the number
        N = len(input_values)
        logger.info(f"Scraping info for {N} values")

        # Save new results here
        results = []

        def cleanup() -> None:
            """Close the web driver."""
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
        def call(i: int) -> None:
            """Call the portal scraper for a specific input value."""
            # Log the number
            if i % self.log_freq == 0:
                logger.debug(i)

            # This input value
            input_value = str(input_values[i])

            # Some DC keys for OIS are shorter
            if self.search_by == "Incident Number":

                # Some DC keys are longer
                if len(input_value) == 12:
                    input_value = input_value[2:]

                # Length should be 10; if not, do nothing
                if len(input_value) != 10:
                    return

            # Scrape!
            scraping_result = self(input_value)

            # Save
            if scraping_result is not None:
                scraping_result_dict = scraping_result.to_dict()["data"]

                # Save results
                results.append(scraping_result_dict)  # Could be empty list

                # Sleep!
                time.sleep(self.sleep)

        # Loop over shootings and scrape
        try:
            for i in range(N):
                call(i)
        except Exception as e:
            # Skip
            if self.errors == "ignore":
                logger.info(
                    f"Exception raised for i = {i} & PDF '{input_values[i]}'"
                )
                logger.info(f"Ignoring exception: {str(e)}")

            # Raise
            else:
                logger.exception(
                    f"Exception raised for i = {i} & PDF '{input_values[i]}'"
                )
                raise
        finally:
            logger.debug(f"Done scraping: {i+1} PDFs scraped")

        return results

    def __call__(self, input_value: str) -> Optional[PortalResults]:
        """
        Scrape data from the portal for a specific input value.

        Parameters
        ----------
        input_value: str
            The value to input into the search portal

        Returns
        -------
        PortalResults
            The scraped data
        """
        # Initialize if we need to
        if not hasattr(self, "driver"):
            self._init()

        # Get the input element selector
        search_by_tag = self.search_by.replace(" ", "")
        SELECTOR = f"{search_by_tag}-Control"

        # The input element
        input_element = self.driver.find_element(
            By.CSS_SELECTOR, f"#{SELECTOR} > input"
        )

        # Clear and add our desired input value
        input_element.clear()
        input_element.send_keys(str(input_value))

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
