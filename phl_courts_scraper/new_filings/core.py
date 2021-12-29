"""Scrape new criminal filings from the First Judicial District."""

from dataclasses import dataclass
from sys import exit
from typing import List

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger

from ..utils import convert_to_floats
from .schema import NewCriminalFilings

URL = "https://www.courts.phila.gov/NewCriminalFilings/date/default.aspx"
SORT_COLUMNS = ["Filing Date", "Docket Number", "Defendant Name"]


@dataclass
class NewFilingsScraper:
    """
    Scrape new criminal filings for First Judicial District.

    Notes
    -----
    See https://www.courts.phila.gov/NewCriminalFilings/date/default.aspx
    """

    def _get_all_dates(self) -> List[str]:
        """Extract the dates from the dropdown."""
        # Parse
        r = requests.get(URL)
        soup = BeautifulSoup(r.text, "html.parser")

        # Parse the option selects, skipping the first one (placeholder text)
        return list(map(lambda x: x.text, soup.select("select option")[1:]))

    def _get_all_pages(self, date: str) -> List[str]:
        """For the specific date, get all page URLs."""
        r = requests.get(URL, params={"search": date})
        soup = BeautifulSoup(r.text, "html.parser")

        return [
            f"https://www.courts.phila.gov/{url}"
            for url in set(
                [a["href"] for a in soup.select(".pagination li a")]
            )
        ]

    def _parse_single_page(self, url: str) -> pd.DataFrame:
        """For the input url, extract the data from the page."""
        # Request the html and parse with beautiful soup
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")

        # The output results
        data = []

        # Loop over each row
        for row in soup.select(".panel-body .row"):

            # Save the result for this row
            result = {}

            # Loop over each column in the row
            for col in row.select(".col-md-4 p"):

                # Extract keys/values in this column
                keys = []
                values = []
                for x in col:
                    s = str(x).strip()

                    # Keys are in bold
                    if "<strong>" in s:
                        keys.append(x.text.strip(":"))
                    # Skip any line breaks
                    elif "<br/>" in s:
                        continue
                    else:
                        # If we have text, its the value
                        if s:
                            if hasattr(x, "text"):
                                s = x.text
                            values.append(s.strip())
                        else:

                            # Bail type is allowed to be empty
                            # If so, add an empty value
                            if (
                                keys[-1] == "Bail Type"
                                and len(values) == len(keys) - 1
                            ):
                                values.append("")

                # Update the result dict for this row
                result.update(dict(zip(keys, values)))

            clean_result = {}
            for k, v in result.items():
                clean_result[k] = v.strip()

            # Save row results
            data.append(clean_result)

        # Return a dataframe
        return pd.DataFrame(data)

    def __call__(self) -> NewCriminalFilings:
        """Run the scraper."""
        # Determine the allowed date range, e.g., the last week
        allowed_dates = self._get_all_dates()

        # Get data from all pages for all dates
        try:
            data = pd.concat(
                map(
                    lambda date: pd.concat(
                        map(self._parse_single_page, self._get_all_pages(date))
                    ),
                    allowed_dates,
                ),
                ignore_index=True,
            ).replace("None", "")
        except Exception as e:
            logger.exception(f"Error parsing data: {str(e)}")
            exit(1)

        logger.info(
            f"Successfully scraped data for {len(data)} criminal filings"
        )

        # Strip extra characters from the data
        for col in data:
            data[col] = data[col].str.strip()

        # Sort
        data = data.sort_values(SORT_COLUMNS)

        # Rename the columns
        data = data.rename(
            columns={
                "Defendant Name": "defendant_name",
                "Age": "age",
                "Address": "address",
                "Docket Number": "docket_number",
                "Filing Date": "filing_date",
                "Charge": "charge",
                "Represented": "represented",
                "Bail Status": "bail_status",
                "Bail Amount": "bail_amount",
                "Bail Date": "bail_date",
                "Bail Type": "bail_type",
                "Outstanding Bail Amt": "outstanding_bail_amount",
            }
        )

        # Check bail type
        if (
            not data["bail_type"]
            .isin(["Monetary", "Unsecured", "ROR", ""])
            .all()
        ):
            logger.exception("Error parsing data: invalid bail types")
            exit(1)

        # Convert to floats
        out = convert_to_floats(
            data, usecols=["bail_amount", "outstanding_bail_amount"]
        )

        return NewCriminalFilings.from_dict(
            {"data": out.to_dict(orient="records")}
        )
