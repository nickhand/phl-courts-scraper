from dataclasses import dataclass
from typing import Iterator, List

import pandas as pd

from ..utils import DataclassSchema


@dataclass
class PortalResult(DataclassSchema):
    """
    A single result returned on the main UJS portal page when
    searching by incident number.

    Parameters
    ----------
    docket_number
    short_caption
    filing_date
    county
    party
    case_status
    otn
    lotn
    dc_number
    date_of_birth
    docket_sheet_url
    court_summary_url
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

    def __repr__(self):
        cls = self.__class__.__name__
        fields = ["docket_number", "filing_date", "party"]
        s = []
        for f in fields:
            s.append(f"{f}='{getattr(self, f)}'")
        s = ", ".join(s)
        return f"{cls}({s})"


@dataclass
class PortalResults(DataclassSchema):
    """
    All of the results returned on the main UJS portal page when
    searching by incident number.

    Parameters
    ----------
    data
    """

    data: List[PortalResult]

    def __iter__(self) -> Iterator[PortalResult]:
        """Yield the object's results."""
        return iter(self.data)

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self.data)

    def __getitem__(self, index):
        """Index the data list."""
        return self.data.__getitem__(index)

    def __repr__(self):
        cls = self.__class__.__name__
        return f"{cls}(num_results={len(self)})"

    def to_pandas(self) -> pd.DataFrame:
        """
        Return a dataframe representation of the data,
        where each row represents a result.
        """
        return pd.DataFrame([c.to_dict() for c in self])
