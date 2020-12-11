from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd
import pdfplumber

from ..utils import Word, find_phrases


def _parse(
    words: List[Word],
    pg: pdfplumber.page.Page,
    start_keyword: str,
    end_keywords: List[str],
    keep_blank_chars: bool = True,
    min_words_vertical: int = 0,
) -> Optional[pd.DataFrame]:

    # Try to find the start phrase
    start_match = find_phrases(words, *start_keyword.split())

    if start_match:

        # Where to start parsing
        start_x = start_match[0].x0
        start_y = start_match[0].top

        # Look for the place to stop
        stop_match = None
        for end_keyword in end_keywords:
            stop_match = find_phrases(words, *end_keyword.split())
            if stop_match:
                break

        if not stop_match:
            raise ValueError("Could not identify end of section")
        stop_y = stop_match[0].top

        # Crop the page
        cropped_pg = pg.crop((start_x, start_y, pg.width, stop_y))

        # Extract the table
        table = cropped_pg.extract_table(
            table_settings=dict(
                vertical_strategy="text",
                horizontal_strategy="text",
                keep_blank_chars=keep_blank_chars,
                min_words_vertical=min_words_vertical,
            )
        )

        # Convert to dataframe
        df = pd.DataFrame(table).replace("", np.nan)

        # Remove empty rows/columns
        df = df.dropna(how="all", axis=1).dropna(how="all", axis=0)

        # First two rows are headers, combine and reset column names
        df = df.loc[2:].rename(
            columns=dict(zip(df.columns, df.loc[0].fillna(df.loc[1]).tolist()))
        )

        return df.reset_index(drop=True)

    return None


@dataclass
class DocketSheetParser:
    """A class to parse docket sheet reports.

    Parameters
    ----------
    path :
        the path to the PDF report to parse
    """

    path: str

    def __call__(self, section: str = "bail") -> Optional[pd.DataFrame]:
        """Parse the docket sheet."""

        allowed_sections = ["bail"]
        if section not in allowed_sections:
            raise ValueError(f"Allowed sections to parse: {allowed_sections}")

        start_keywords = {"bail": "Bail Action"}
        stop_keywords = {"bail": ["CHARGES", "CPCMS"]}

        # Open the PDF
        out = None
        with pdfplumber.open(self.path) as pdf:

            # Loop through pages
            for pg in pdf.pages:

                # Get the list of words
                words = [
                    Word.from_dict(word_dict)
                    for word_dict in pg.extract_words(keep_blank_chars=False)
                ]

                # Try to parse
                result = _parse(
                    words, pg, start_keywords[section], stop_keywords[section]
                )

                # Return any results
                if result is not None:
                    out = result
                    break

        if out is None:
            raise ValueError("Parsing failed!")

        return out
