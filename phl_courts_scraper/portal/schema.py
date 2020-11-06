from dataclasses import dataclass
from typing import Iterator, List, Optional

from ..utils import DataclassBase


@dataclass
class PortalResult(DataclassBase):
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
    short_caption: str
    filing_date: str
    county: str
    party: str
    case_status: str
    otn: str
    lotn: str
    dc_number: str
    date_of_birth: str
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
class PortalResults(DataclassBase):
    """
    All of the results returned on the main UJS portal page when
    searching by incident number.

    Parameters
    ----------
    data
    """

    data: List[Optional[PortalResult]]

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
