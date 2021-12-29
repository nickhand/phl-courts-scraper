from dataclasses import dataclass
from typing import Iterator, List

import pandas as pd

from ..utils import DataclassSchema


@dataclass
class PortalResult(DataclassSchema):
    """
    The scraped result from the UJS portal page.

    Parameters
    ----------
    docket_number: str
        The docket number of the case
    short_caption: str
        The short caption of the case
    filing_date: str
        The filing date of the case
    county: str
        The county of the case
    party: str
        The party of the case
    case_status: str
        The current case status
    otn: str
        The offense tracking number
    lotn: str
        The law tracking number
    dc_number: str
        The DC number
    date_of_birth: str
        The date of birth of the party
    docket_sheet_url: str
        The docket sheet URL
    court_summary_url: url
        The court summary URL
    """

    docket_number: str
    court_type: str
    short_caption: str
    case_status: str
    filing_date: str
    party: str
    date_of_birth: str
    county: str
    court_office: str
    otn: str
    lotn: str
    dc_number: str
    docket_sheet_url: str
    court_summary_url: str

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        cls = self.__class__.__name__
        fields = ["docket_number", "filing_date", "party"]
        s = []
        for f in fields:
            s.append(f"{f}='{getattr(self, f)}'")
        out = ", ".join(s)
        return f"{cls}({out})"


@dataclass
class PortalResults(DataclassSchema):
    """
    List of results from portal scraping.

    Parameters
    ----------
    data: List[PortalResult]
        The list of results
    """

    data: List[PortalResult]

    def __iter__(self) -> Iterator[PortalResult]:
        """Yield the object's results."""
        return iter(self.data)

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self.data)

    def __getitem__(self, index: int) -> PortalResult:
        """Index the data list."""
        return self.data.__getitem__(index)

    def __repr__(self) -> str:
        """Return the string representation of the object."""
        cls = self.__class__.__name__
        return f"{cls}(num_results={len(self)})"

    def to_pandas(self) -> pd.DataFrame:
        """Return a dataframe representation of the data."""
        return pd.DataFrame([c.to_dict() for c in self])
