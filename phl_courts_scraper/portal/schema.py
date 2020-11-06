from dataclasses import dataclass
from typing import Optional

from ..utils import DataclassBase


@dataclass
class PortalSummary(DataclassBase):
    """
    The results returned on the main UJS portal page when
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
