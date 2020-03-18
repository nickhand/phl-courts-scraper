from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import Select
from typing import List, Optional, Callable


def any_of(*expected_conditions: Callable) -> Callable[[object], bool]:
    """An expectation that any of multiple expected conditions is true.
    Equivalent to a logical 'OR'.
    Returns results of the first matching condition, or False if none do."""

    def any_of_condition(driver: WebDriver) -> bool:
        for expected_condition in expected_conditions:
            try:
                result = expected_condition(driver)
                if result:
                    return result
            except WebDriverException:
                pass
        return False

    return any_of_condition


def initialize_incident_scrape(driver: WebDriver) -> None:

    # navigate to the portal URL
    URL = "https://ujsportal.pacourts.us/DocketSheets/MC.aspx"
    driver.get(URL)

    # select the search by dropdown element
    SEARCH_BY_DROPDOWN = "ctl00_ctl00_ctl00_cphMain_cphDynamicContent_cphDynamicContent_searchTypeListControl"
    input_searchtype = Select(
        driver.find_element_by_xpath(f'//*[@id="{SEARCH_BY_DROPDOWN}"]')
    )

    # Search by police incident
    input_searchtype.select_by_visible_text("Police Incident/Complaint Number")


def scrape_data_by_incident(
    driver: WebDriver, dc_number: str
) -> Optional[List[dict]]:
    """
    Given an input DC number for a police incident, return
    the relevant details from the courts portal.

    Parameters
    ----------
    driver : WebDriver
        the selenium driver instance
    dc_number : str
        the unique identifier for the police incident

    Returns
    -------
    results : list
        a list of dictionaries holding details for each unique docket number
    """

    # Get the input element for the DC number
    INPUT_DC_NUMBER = "ctl00_ctl00_ctl00_cphMain_cphDynamicContent_cphDynamicContent_policeIncidentNumberCriteriaControl_policeIncidentNumberControl"
    input_dc_number = driver.find_element_by_xpath(
        f'//*[@id="{INPUT_DC_NUMBER}"]'
    )

    # Clear and add our desired DC number
    input_dc_number.clear()
    input_dc_number.send_keys(str(dc_number))

    # Submit the search
    SEARCH_BUTTON = "ctl00_ctl00_ctl00_cphMain_cphDynamicContent_cphDynamicContent_policeIncidentNumberCriteriaControl_searchCommandControl"
    driver.find_element_by_xpath(f'//*[@id="{SEARCH_BUTTON}"]').click()

    # Results / no results elements
    RESULTS_CONTAINER = "ctl00_ctl00_ctl00_cphMain_cphDynamicContent_cphDynamicContent_policeIncidentNumberCriteriaControl_searchResultsGridControl_resultsPanel"
    NO_RESULTS_CONTAINER = "ctl00_ctl00_ctl00_cphMain_cphDynamicContent_cphDynamicContent_policeIncidentNumberCriteriaControl_searchResultsGridControl_noResultsPanel"

    # Wait explicitly until search results load
    WebDriverWait(driver, 120).until(
        any_of(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"#{RESULTS_CONTAINER}")
            ),
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"#{NO_RESULTS_CONTAINER}")
            ),
        )
    )

    # if results succeeded, parse them
    out = None
    try:
        # Table holding the search results
        results_table = driver.find_element_by_xpath(
            f'//*[@id="{RESULTS_CONTAINER}"]/table'
        )

        # The rows of the search page
        results_rows = results_table.find_elements_by_css_selector(
            "tbody > tr.gridViewRow"
        )

        # result fields
        fields = [
            "docket_number",
            "short_caption",
            "filing_date",
            "county",
            "party",
            "case_status",
            "otn",
            "lotn",
            "dc_number",
            "date_of_birth",
        ]

        # extract data for each row, including links
        out = []
        for row in results_rows:

            # the data displayed in the row itself
            texts = [aa.text for aa in row.find_elements_by_css_selector("td")]
            X = dict(zip(fields, texts[-len(fields) :]))

            # the urls to the court summary and docket sheet
            urls = [
                a.get_attribute("href")
                for a in row.find_elements_by_css_selector("a")
            ]
            X["court_summary_url"] = urls[-1]
            X["docket_sheet_url"] = urls[-2]
            out.append(X)
    except NoSuchElementException:
        pass

    return out
