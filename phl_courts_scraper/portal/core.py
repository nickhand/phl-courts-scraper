"""Scrape data from the PA Unified Judicial System portal."""

import random
from dataclasses import dataclass
from typing import Callable, List, Optional

from loguru import logger
from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from tryagain import retries

from .schema import PortalResults

__all__ = ["UJSPortalScraper"]

# The URL of the portal
PORTAL_URL = "https://ujsportal.pacourts.us/CaseSearch"


@dataclass
class UJSPortalScraper:
    """Scrape the UJS courts portal by incident number.

    Parameters
    ----------
    driver :
        the selenium web driver that runs the scraping
    url :
        the url to scrape; default is the municipal courts UJS portal
    """

    driver: WebDriver
    url: str = PORTAL_URL

    def __post_init__(self):
        """Prepare the web scraper to scrape by incident number."""

        # navigate to the portal URL
        self.driver.get(self.url)

    def _prep_url(self):
        """Prep the URL for scraping."""

        # select the search by dropdown element
        SEARCH_BY_DROPDOWN = "SearchBy-Control"
        input_searchtype = Select(
            self.driver.find_element_by_css_selector(
                f"#{SEARCH_BY_DROPDOWN} > select"
            )
        )

        # Search by police incident
        input_searchtype.select_by_visible_text("Incident Number")

    def __call__(
        self, dc_number: str, max_sleep=120, min_sleep=30
    ) -> Optional[PortalResults]:
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

        def retry_hook():
            logger.info("Refreshing!")
            self.driver.refresh()
            logger.info("   Done refreshing!")

            logger.info("Prepping URL...")
            self._prep_url()
            logger.info("...done")

        @retries(
            max_attempts=10,
            cleanup_hook=lambda: logger.info("Retrying..."),
            pre_retry_hook=retry_hook,
            wait=lambda n: min(
                min_sleep + 2 ** n + random.random(), max_sleep
            ),
        )
        def _call():

            # Get the input element for the DC number
            INPUT_DC_NUMBER = "IncidentNumber-Control"
            input_dc_number = self.driver.find_element_by_css_selector(
                f"#{INPUT_DC_NUMBER} > input"
            )

            # Clear and add our desired DC number
            input_dc_number.clear()
            input_dc_number.send_keys(str(dc_number))

            # Submit the search
            SEARCH_BUTTON = "btnSearch"
            self.driver.find_element_by_css_selector(
                f"#{SEARCH_BUTTON}"
            ).click()

            # Results / no results elements
            RESULTS_CONTAINER = "caseSearchResultGrid"

            # Wait explicitly until search results load
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, f"#{RESULTS_CONTAINER}")
                ),
            )

            # if results succeeded, parse them
            out = None
            try:
                # Table holding the search results
                results_table = self.driver.find_element_by_css_selector(
                    f"#{RESULTS_CONTAINER}"
                )

                # The rows of the search page
                results_rows = results_table.find_elements_by_css_selector(
                    "tbody > tr"
                )

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
                        aa.text
                        for aa in row.find_elements_by_css_selector("td")
                        if aa.get_attribute("class") != "display-none"
                    ]

                    # No text? Skip!
                    if not len(texts):
                        continue

                    # Make sure we check the length
                    # Last td cell is unnecessary — it holds the urls (added below)
                    assert len(texts) == len(fields) + 1
                    X = dict(zip(fields, texts[:-1]))

                    # the urls to the court summary and docket sheet
                    urls = [
                        a.get_attribute("href")
                        for a in row.find_elements_by_css_selector("a")
                    ]
                    X["court_summary_url"] = urls[-1]
                    X["docket_sheet_url"] = urls[-2]

                    # Save it
                    data.append(X)

                # Return a Portal Results
                out = PortalResults.from_dict({"data": data})

            except NoSuchElementException:
                pass

            return out

        return _call()
