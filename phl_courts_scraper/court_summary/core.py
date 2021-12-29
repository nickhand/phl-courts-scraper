"""Module for parsing court summary reports."""

import collections
from operator import itemgetter
from pathlib import Path
from typing import Any

from ..base import DownloadedPDFScraper
from ..utils import get_pdf_words
from . import utils
from .schema import CourtSummary


class CourtSummaryParser(DownloadedPDFScraper):
    """
    A class to parse court summary reports.

    Call the class to parse a PDF. The class will return a
    CourtSummary object.


    Example
    -------
    >>> from phl_courts_scraper.court_summary import CourtSummaryParser
    >>> parser = CourtSummaryParser()
    >>> court_summary = parser(pdf_path)
    """

    def __call__(self, pdf_path: Path, **kwargs: Any) -> CourtSummary:
        """Parse and return a court summary document."""
        # Parse PDF into a list of words
        words = get_pdf_words(
            str(pdf_path),
            keep_blank_chars=True,
            x_tolerance=5,
            y_tolerance=0,
            header_cutoff=0,
            footer_cutoff=645,
        )

        # Define the section headers
        headers = [
            "Active",
            "Closed",
            "Inactive",
            "Archived",
            "Adjudicated",
        ]

        # Determine section headers
        starts = {}
        for header in headers:
            line = utils.find_line_number(words, header, missing="ignore")
            if line is not None:
                starts[header] = line

        # Put the section in the correct order (ascending)
        sections = sorted(starts, key=itemgetter(1))
        sorted_starts = collections.OrderedDict()
        for key in sections:
            sorted_starts[key] = starts[key]

        # Parse each section
        dockets = []
        for i, this_section in enumerate(sorted_starts):

            # Skip the "Archived" section
            if this_section == "Archived":
                continue

            # Determine the next section if there is one
            next_section = sections[i + 1] if i < len(sections) - 1 else None

            # Determine line number of sections
            this_section_start = sorted_starts[this_section]
            next_section_start = (
                sorted_starts[next_section] if next_section else None
            )

            # Trim the words to just lines in this section
            section_words = words[this_section_start:next_section_start]

            # Parse dockets in this section
            for docket_number, county, docket in utils.yield_dockets(
                section_words
            ):

                # Do the parsing work
                result = utils.parse_charges_table(docket_number, docket)

                # Format the result
                info = result["header"]
                info["county"] = county
                info["docket_number"] = docket_number
                info["status"] = this_section.lower()
                info["charges"] = result["charges"]

                # Fix columns
                if "prob_#" in info:
                    info["prob_num"] = info.pop("prob_#")
                if "psi#" in info:
                    info["psi_num"] = info.pop("psi#")

                # Save the result
                dockets.append(info)

        # Parse the header too
        out = utils.parse_header(words, sections[0])
        out["dockets"] = dockets

        return CourtSummary.from_dict(out)
