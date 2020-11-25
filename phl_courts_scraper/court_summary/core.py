"""Module for parsing court summary reports."""

import collections
from dataclasses import dataclass
from operator import attrgetter, itemgetter
from typing import List, Optional, Tuple, Union

from ..utils import (
    Word,
    find_nearest,
    get_pdf_words,
    group_into_lines,
    groupby,
    to_snake_case,
)
from .schema import CourtSummary

__all__ = ["CourtSummaryParser"]

COUNTY_CODES = {
    "1": "Adams",
    "35": "Lackawanna",
    "2": "Allegheny",
    "36": "Lancaster",
    "3": "Armstrong",
    "37": "Lawrence",
    "4": "Beaver",
    "38": "Lebanon",
    "5": "Bedford",
    "39": "Lehigh",
    "6": "Berks",
    "40": "Luzerne",
    "7": "Blair",
    "41": "Lycoming",
    "8": "Bradford",
    "42": "McKean",
    "9": "Bucks",
    "43": "Mercer",
    "10": "Butler",
    "44": "Mifflin",
    "11": "Cambria",
    "45": "Monroe",
    "12": "Cameron",
    "46": "Montgomery",
    "13": "Carbon",
    "47": "Montour",
    "14": "Centre",
    "48": "Northampton",
    "15": "Chester",
    "49": "Northumberland",
    "16": "Clarion",
    "50": "Perry",
    "17": "Clearfield",
    "51": "Philadelphia",
    "18": "Clinton",
    "52": "Pike",
    "19": "Columbia",
    "53": "Potter",
    "20": "Crawford",
    "54": "Schuylkill",
    "21": "Cumberland",
    "55": "Snyder",
    "22": "Dauphin",
    "56": "Somerset",
    "23": "Delaware",
    "57": "Sullivan",
    "24": "Elk",
    "58": "Susquehanna",
    "25": "Erie",
    "59": "Tioga",
    "26": "Fayette",
    "60": "Union",
    "27": "Forest",
    "61": "Venango",
    "28": "Franklin",
    "62": "Warren",
    "29": "Fulton",
    "63": "Washington",
    "30": "Greene",
    "64": "Wayne",
    "31": "Huntingdon",
    "65": "Westmoreland",
    "32": "Indiana",
    "66": "Wyoming",
    "33": "Jefferson",
    "67": "York",
    "34": "Juniata",
}


def _vertically_aligned(x0, x1, tol=3):
    return abs(x0 - x1) <= tol


def _horizontally_aligned(y0, y1, tol=3):
    return abs(y0 - y1) <= tol


def _get_line_as_dict(header, line):

    r = {}
    header_values = [w.text for w in header]
    for iline in range(len(line)):
        w = line[iline]
        nearest = find_nearest([h.x for h in header], w.x)
        r[header_values[nearest]] = w.text
    return r


def _parse_raw_docket(
    docket_number: str, words: List[Word]
) -> Tuple[str, dict]:
    """Parse the raw docket words.

    Returns
    -------
    docket_number :
        the docket number
    info :
        dict holding header info and charges info
    """

    # Determine headers
    headers = [
        "Seq No",
        "Statute",
        "Grade",
        "Description",
        "Disposition",
        "Sentence Dt.",
        "Sentence Type",
        "Program Period",
        "Sentence Length",
    ]
    header_tuples = [w for w in words if w.text in headers]

    # Analyze the header setup
    H = {}
    for aa, bb in groupby(header_tuples, "y"):
        H[aa] = list(bb)

    # Get all header rows
    header_lines = list(H.values())

    # Determine unique ones and multiheader status
    header_values = []
    keep = []
    for i, elem in enumerate(header_lines):
        texts = [w.text for w in elem]
        if texts not in header_values:
            header_values.append(texts)
            keep.append(i)

    header_lines = [line for (i, line) in enumerate(header_lines) if i in keep]

    unique_header_nrows = len(header_lines)
    multiline_header = unique_header_nrows > 1
    if multiline_header:
        assert unique_header_nrows == 2

    # Split into docket header and body
    docket_header, docket_body = _parse_docket_header(docket_number, words)

    # Format the rest
    header_info = [
        [s.strip() for s in w.text.split(":")] for w in docket_header[1:]
    ]

    # IMPORTANT: ensure that ":" split gave us two fields
    extra = []
    for i in reversed(range(0, len(header_info))):
        value = header_info[i]
        if len(value) != 2:
            value = header_info.pop(i)
            if value[0] != docket_number:
                extra.append(value)

    # Convert to dict
    header_info = dict(header_info)

    # Parse the docket body
    results = []
    if len(docket_body):

        # Group into lines
        lines = group_into_lines(docket_body, tolerance=3)
        lines_y = sorted(lines)  # the y-values (keys of lines)

        # Determine indents of rows
        row = None
        for i, y in enumerate(lines_y):

            # This is the line
            line = lines[y]
            start = line[0].x  # First x value in line

            # If this line is a header line, skip it!
            if [w.text for w in line] in header_values:
                continue

            # Skip if first line is docket number
            # This skips any extra header lines continued on multiple pages
            if line[0].text == docket_number:
                continue

            # Start of new charge
            if line[0].text.isdigit() and _vertically_aligned(
                line[0].x, header_lines[0][0].x, tol=1
            ):

                if row is not None:
                    results.append(row)

                # Header and line as dict
                header = header_lines[0]
                line_dict = _get_line_as_dict(header, line)

                row = line_dict.copy()
                row["sentences"] = []

            else:
                if multiline_header and _vertically_aligned(
                    start, header_lines[1][0].x, tol=1
                ):
                    # Header and line as dict
                    header = header_lines[1]
                    line_dict = _get_line_as_dict(header, line)

                    row["sentences"].append(line_dict)
                else:

                    line_dict = _get_line_as_dict(header, line)

                    for key in line_dict:
                        if key in row:
                            row[key] += " " + line_dict[key]
                        elif key in row["sentences"]:
                            row["sentences"][key] += " " + line_dict[key]

            if i == len(lines_y) - 1:
                results.append(row)

    # Format the string keys in header
    header_info = to_snake_case(header_info)
    header_info["extra"] = extra

    # Format the string keys in results
    results = [to_snake_case(r) for r in results]
    for r in results:
        r["sentences"] = [to_snake_case(d) for d in r["sentences"]]

    return {"header": header_info, "charges": results}


def _parse_header(words: List[Word], firstSectionTitle: str) -> dict:
    """Parse the header component of the court summary."""

    # Get the line number containing "Active"
    i = _find_line_numbers(words, firstSectionTitle)

    out = []
    for key, val in groupby(words[:i], "x", sort=True):
        val = sorted(val, key=attrgetter("x"), reverse=True)  # sort by x
        out.append((key, val))

    info = sorted(out, key=lambda t: min(tt.y for tt in t[1]))  # sort by min y
    info = info[2:]  # Drop info we don't need

    out = {}
    row = info[0]
    out["date_of_birth"] = row[-1][0].text.split(":")[-1].strip()

    # Get parameters that have format "Key: Value"
    for w in info[1][-1]:
        key, value = w.text.split(":")
        out[key.strip().lower()] = value.strip().lower()

    # Finish up
    row = info[2]
    out["name"] = row[-1][0].text.strip()
    out["location"] = row[-1][1].text.strip()
    out["aliases"] = [w.text.strip() for w in row[-1][3:]]

    return out


def _parse_docket_header(
    docket_number: str, words: List[Word]
) -> Tuple[List[Word], List[Word]]:
    """Parse the header of a particular docket.

    Parameters
    ----------
    words :
        the list of words

    Returns
    -------
    docket_header :
        the words containing the docket header
    docket_body :
        the body of the docket; this is optional
    """

    # Group into common y values
    grouped = [list(group) for _, group in groupby(words, "y")]
    grouped = [item for sublist in grouped for item in sublist]

    i = _find_line_numbers(grouped, "Seq No", missing="ignore")

    # If this is missing: docket continues on multiple pages
    if i == []:
        return grouped, []
    else:  # split into header/body -- docket is on one page
        return grouped[:i], grouped[i:]


def _find_line_numbers(
    words: List[Word],
    text: str,
    how: str = "equals",
    return_all: bool = False,
    missing: str = "raise",
) -> Union[List[int], int]:
    """Return the line numbers associated with a specific text.

    Parameters
    ----------
    words :
        the list of words to check against
    text :
        the word text to search for
    how :
        how to do the comparison; either "equals" or "contains"
    return_all :
        whether to return line numbers of all matches or just the
        first match
    missing :
        if no matches are found, either raise an Exception, or
        return an empty list

    Returns
    -------
    line_numbers :
        the line numbers, either all or the first match
    """
    assert how in ["equals", "contains"]

    def contains(a, b):
        return b in a

    def equals(a, b):
        return a == b

    if how == "equals":
        tester = equals
    else:
        tester = contains

    # Test each word
    listOfElements = [tester(w.text, text) for w in words]
    indexPosList = []
    indexPos = 0
    while True:
        try:
            # Search for item in list from indexPos to the end of list
            indexPos = listOfElements.index(True, indexPos)
            # Add the index position in list
            indexPosList.append(indexPos)
            indexPos += 1
        except ValueError:
            break

    if len(indexPosList) == 0:
        if missing == "raise":
            raise ValueError("No text matches found")
        else:
            return []

    if not return_all:
        indexPosList = indexPosList[0]
    return indexPosList


def _yield_dockets(dockets: List[Word]) -> List[Word]:
    """
    Yield words associated with all of the unique dockets,
    separated by docket numbers in the input list of words.

    Parameters
    ----------
    words :
        the list of words to parse

    Yields
    ------
    docket :
        the words for each docket
    """
    # Delete any headers
    max_header_size = 5
    for pg in reversed(
        _find_line_numbers(
            dockets,
            "First Judicial District of Pennsylvania",
            return_all=True,
            missing="ignore",
        )
    ):
        # Loop over header row
        # REMOVE: any "Continued" lines of FJD / Court Summary header
        for i in reversed(range(0, max_header_size)):

            if pg + i < len(dockets) - 1:
                w = dockets[pg + i]
                if (
                    w.text
                    in [
                        "First Judicial District of Pennsylvania",
                        "Court Summary",
                    ]
                    or "Continued" in w.text
                ):
                    del dockets[pg + i]

    # Get docket numbers
    docket_info = [
        (i, w.text)
        for i, w in enumerate(dockets)
        if w.text.startswith("MC-") or w.text.startswith("CP-")
    ]

    indices, docket_numbers = list(zip(*docket_info))

    indices = list(indices) + [None]

    # Yield the parts for each docket
    returned = []
    for i in range(len(indices) - 1):

        # This docket number
        this_docket_num = docket_numbers[i]

        # Skip dockets we've already returned
        if this_docket_num in returned:
            continue

        # Determine the index of when the next one starts
        j = i + 1
        while j < len(docket_numbers) and this_docket_num == docket_numbers[j]:
            j += 1

        start = indices[i]
        stop = indices[j]

        # Determine county
        county_code = int(this_docket_num.split("-")[1])
        county = COUNTY_CODES[str(county_code)]

        # Return
        yield this_docket_num, county, dockets[start:stop]

        # Track which ones we've returned
        returned.append(this_docket_num)


@dataclass
class CourtSummaryParser:
    """A class to parse court summary reports.

    Parameters
    ----------
    path :
        the path to the PDF report to parse
    """

    path: str

    def __call__(self):
        """Parse and return a court summary document."""

        # Parse PDF into a list of words
        words = get_pdf_words(self.path)

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
            line = _find_line_numbers(words, header, missing="ignore")
            if line != []:
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
            for docket_number, county, docket in _yield_dockets(section_words):

                # Do the parsing work
                result = _parse_raw_docket(docket_number, docket)

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
        out = _parse_header(words, sections[0])
        out["dockets"] = dockets

        return CourtSummary.from_dict(out)
