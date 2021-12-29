"""Define the schema for the docket sheet scraper."""
# from dataclasses import dataclass
# from typing import Iterator, List, Optional

# import pandas as pd

# from ..utils import DataclassSchema


# @dataclass
# class BailResult(DataclassSchema):
#     """
#     A single result returned when scraping bail info from
#     a docket sheet

#     Parameters
#     ----------

#     """

#     bail_action: str
#     bail_date: str
#     bail_type: str
#     percentage: str
#     amount: str
#     bail_posting_status: Optional[str]
#     posting_date: Optional[str]


# @dataclass
# class DocketSheetResults(DataclassSchema):
#     """
#     All of the results scraped from a list of docket sheets.

#     Parameters
#     ----------
#     data
#     """

#     data: List[BailResult]

#     def __iter__(self) -> Iterator[BailResult]:
#         """Yield the object's results."""
#         return iter(self.data)

#     def __len__(self) -> int:
#         """Return the number of results."""
#         return len(self.data)

#     def __getitem__(self, index):
#         """Index the data list."""
#         return self.data.__getitem__(index)

#     def __repr__(self):
#         cls = self.__class__.__name__
#         return f"{cls}(num_results={len(self)})"

#     def to_pandas(self) -> pd.DataFrame:
#         """
#         Return a dataframe representation of the data,
#         where each row represents a result.
#         """
#         return pd.DataFrame([c.to_dict() for c in self])
