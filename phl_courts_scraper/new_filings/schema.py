"""Schema for new criminal filing scraper."""

from dataclasses import dataclass
from typing import Iterator, List, Optional

import desert
import numpy as np
import pandas as pd

from ..utils import DataclassSchema, TimeField


@dataclass
class NewCriminalFiling(DataclassSchema):
    """
    The scraped result from the UJS portal page.

    Parameters
    ----------
    defendant_name: str
        The name of the defendant
    age: str
        The age of the defendant
    address: str
        The defendant's address
    docket_number: str
        The docket number
    filing_date: str
        The date the filing was filed
    charge: str
        The criminal charge
    represented: str
        The name of the person who represented the defendant
    bail_status: str
        The current bail status
    """

    defendant_name: str
    age: str
    address: str
    docket_number: str
    filing_date: str
    charge: str
    bail_date: str = desert.field(
        TimeField(format="%m/%d/%Y %H:%M:%S %p", allow_none=True)
    )  # type: ignore
    represented: Optional[str] = None
    bail_type: Optional[str] = None
    outstanding_bail_amount: Optional[float] = None
    bail_amount: Optional[float] = None
    bail_status: Optional[str] = None
    in_custody: Optional[str] = None

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        cls = self.__class__.__name__
        fields = ["docket_number", "filing_date", "defendant_name"]
        s = []
        for f in fields:
            s.append(f"{f}='{getattr(self, f)}'")
        out = ", ".join(s)
        return f"{cls}({out})"


@dataclass
class NewCriminalFilings(DataclassSchema):
    """
    List of results from portal scraping.

    Parameters
    ----------
    data: List[NewCriminalFiling]
        The list of results
    """

    data: List[NewCriminalFiling]

    def __iter__(self) -> Iterator[NewCriminalFiling]:
        """Yield the object's results."""
        return iter(self.data)

    def __len__(self) -> int:
        """Return the number of results."""
        return len(self.data)

    def __getitem__(self, index: int) -> NewCriminalFiling:
        """Index the data list."""
        return self.data.__getitem__(index)

    def __repr__(self) -> str:
        """Return the string representation of the object."""
        cls = self.__class__.__name__
        return f"{cls}(num_results={len(self)})"

    def to_pandas(self) -> pd.DataFrame:
        """Return a dataframe representation of the data."""
        return pd.DataFrame([c.to_dict() for c in self]).replace(
            {None: np.nan, "": np.nan}
        )
