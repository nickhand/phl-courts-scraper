"""Module for scraping utilities."""

import re
from operator import attrgetter
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..utils import (
    Word,
    find_nearest,
    group_into_lines,
    groupby,
    to_snake_case,
)

# FIPS county codes for PA
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


def check_abs_diff(x0: float, x1: float, tol: float = 3) -> bool:
    """
    Check absolute difference between two numbers.

    This will test if the absolute difference between two numbers is
    within a certain tolerance.

    Parameters
    ----------
    x0, x1: float
        the numbers to difference
    tol: float
        the tolerance (inclusive)

    Returns
    -------
    bool:
        True if the absolute difference is within the tolerance
    """
    return abs(x0 - x1) <= tol


def find_word_headers(line: List[Word], header: List[Word]) -> Dict[str, str]:
    """
    Map words in a line to the corresponding header words.

    Given a line and the header for that line, find the correct
    column for each line word, and return a dictionary of keys/values.

    Parameters
    ----------
    line: List[Word]
        The line of words to return as a dict
    header: List[Word]
        The header line to use to determine column headers

    Returns
    -------
    Dict[str, str]:
        The line in dict form, with column headers as keys and word text
        as values
    """
    out = {}

    # These are the column headers
    column_headers = [w.text for w in header]
    header_x = [w.x for w in header]

    # Find the nearest column header and save
    for i in range(len(line)):

        # Find the index of the nearest column match
        word = line[i]
        nearest = find_nearest(header_x, word.x)

        # The matching column header
        col = column_headers[nearest]

        # Save
        out[col] = word.text

    return out


def parse_charges_table(
    docket_number: str, words: List[Word]
) -> Dict[str, Any]:
    """
    Parse the raw docket words into a dict of header and charges.

    Parameters
    ----------
    docket_number: str
        The docket number
    words: List[Word]
        The list of words in the raw dockets

    Returns
    -------
    result :
        A dict with keys "header" holding the header info for the docket
        and "charges" holding the charge information
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
    header_values: List[List[str]] = []
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
    docket_header, docket_body = parse_docket_header(words)

    # Format the rest
    header_info: List[Tuple[str, ...]] = [
        tuple(s.strip() for s in w.text.split(":")) for w in docket_header[1:]
    ]

    # IMPORTANT: ensure that ":" split gave us two fields
    extra: List[str] = []
    header_info_dict: Dict[str, Any] = {}
    for i in reversed(range(0, len(header_info))):
        value = header_info[i]

        # Save any extra info that wasn't
        if len(value) != 2:

            # Remove it
            value = header_info.pop(i)

            # Save it
            if value[0] != docket_number:
                extra += value

        else:
            header_info_dict[value[0]] = value[1]

    # Parse the docket body
    charges = []
    if len(docket_body):

        # Group into lines
        lines = group_into_lines(docket_body, tolerance=3)
        lines_y = sorted(lines)  # the y-values (keys of lines)

        # Determine indents of rows
        row: Dict[str, Any] = {}
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

            # ----------------------------------------------
            # OPTION 1: Start of new charge
            # ----------------------------------------------
            if line[0].text.isdigit() and check_abs_diff(
                line[0].x, header_lines[0][0].x, tol=1
            ):

                if len(row):
                    charges.append(row)

                # Header is first line in header
                header = header_lines[0]

                # Create the row object with the line data
                row = find_word_headers(line, header)
                row["sentences"] = []  # type: ignore

            # ----------------------------------------------
            # OPTION 2: Parsing continuation of a line
            # ----------------------------------------------
            else:
                # ------------------------------------------
                # OPTION 2A: This is a new sentence
                # ------------------------------------------
                if multiline_header and check_abs_diff(
                    start, header_lines[1][0].x, tol=1
                ):

                    # Header is the second line of header
                    header = header_lines[1]

                    # Parse the line into a dict
                    line_dict = find_word_headers(line, header)

                    # Save to a list of sentences
                    row["sentences"].append(line_dict)

                # -------------------------------------------
                # OPTION 2B: Field is continue onto new line
                # -------------------------------------------
                else:

                    # Parse this line
                    line_dict = find_word_headers(line, header)

                    # Search for the the field that was continued
                    for key in line_dict:
                        if key in row:
                            row[key] += " " + line_dict[key]
                        elif key in row["sentences"]:
                            row["sentences"][key] += " " + line_dict[key]

            # Last line? Save it!
            if i == len(lines_y) - 1:
                charges.append(row)

    # Format the string keys in header
    header_info_dict = to_snake_case(header_info_dict)
    header_info_dict["extra"] = extra  # type: ignore

    # Format the string keys in results
    charges = [to_snake_case(charge) for charge in charges]
    for charge in charges:
        charge["sentences"] = [to_snake_case(s) for s in charge["sentences"]]

    return {"header": header_info_dict, "charges": charges}


def parse_header(words: List[Word], firstSectionTitle: str) -> Dict[str, Any]:
    """Parse the header component of the court summary."""
    # Get the line number containing "Active"
    i = find_line_number(words, firstSectionTitle)

    # Get the line that says "Court Summary"
    j = find_line_number(words, "Court Summary")
    assert j is not None

    # Trim to header valid range
    header_words = words[j + 1 : i]

    info = []
    for key, val in groupby(header_words, "x", sort=True):
        sorted_val = sorted(
            val, key=attrgetter("x"), reverse=True
        )  # sort by x
        info.append((key, sorted_val))

    out: Dict[str, Any] = {}
    row = info[1]
    out["date_of_birth"] = row[-1][0].text.split(":")[-1].strip()

    # Get parameters that have format "Key: Value"
    for w in info[2][-1]:
        k, v = w.text.split(":")
        out[k.strip().lower()] = v.strip().lower()

    # Finish up
    row = info[0]
    out["name"] = row[-1][0].text.strip()
    out["location"] = row[-1][1].text.strip()
    out["aliases"] = [w.text.strip() for w in row[-1][3:]]

    return out


def parse_docket_header(words: List[Word]) -> Tuple[List[Word], List[Word]]:
    """
    Parse the header of a particular docket.

    Parameters
    ----------
    words: List[Word]
        The list of words

    Returns
    -------
    docket_header: List[Word]
        The words containing the docket header
    docket_body: List[Word]
        The body of the docket
    """,
    # Group into common y values
    grouped = [list(group) for _, group in groupby(words, "y")]
    grouped_flat = [item for sublist in grouped for item in sublist]

    # Find the line number that says "Seq No"
    i = find_line_number(grouped_flat, "Seq No", missing="ignore")

    # If this is missing: docket continues on multiple pages
    if i is None:
        return grouped_flat, []
    else:  # split into header/body -- docket is on one page
        return grouped_flat[:i], grouped_flat[i:]


def find_line_number(
    words: List[Word],
    text: str,
    how: str = "equals",
    missing: str = "raise",
) -> Optional[int]:
    """Return the first line number associated with a specific text.

    Parameters
    ----------
    words: List[Word]
        The list of words to check against
    text: str
        The word text to search for
    how: str
        How to do the comparison; either "equals", "contains",
        or 'regex'
    missing: str
        Ff no matches are found, either raise an Exception, or
        return an empty list

    Returns
    -------
    line_number: int
        The first matching line number, or None if no matches
    """
    indexPosList = find_line_numbers(words, text, how=how, missing=missing)
    if len(indexPosList) == 0:
        return None
    return indexPosList[0]


def find_line_numbers(
    words: List[Word],
    text: str,
    how: str = "equals",
    missing: str = "raise",
) -> List[int]:
    """Return the line numbers associated with a specific text.

    Parameters
    ----------
    words: List[Word]
        The list of words to check against
    text: str
        The word text to search for
    how: str
        How to do the comparison; either "equals", "contains",
        or 'regex'
    missing: str
        If no matches are found, either raise an Exception, or
        return an empty list

    Returns
    -------
    List[int]
        a list of line numbers matching the text

    Raises
    ------
    ValueError
        If there are no matches
    """
    assert how in ["equals", "contains", "regex"]

    def contains(a: str, b: str) -> bool:
        """Test if b in a."""
        return b in a

    def equals(a: str, b: str) -> bool:
        """Test if a == b."""
        return a == b

    def matches(a: str, b: str) -> bool:
        """Test if if b matches the regex pattern a."""
        return re.match(b, a) is not None

    if how == "equals":
        tester = equals
    elif how == "contains":
        tester = contains
    else:
        tester = matches

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

    if len(indexPosList) == 0 and missing == "raise":
        raise ValueError("No text matches found")

    return indexPosList


def yield_dockets(
    dockets: List[Word],
) -> Iterator[Tuple[str, str, List[Word]]]:
    """
    Yield words associated with all of the unique dockets.

    Dockets are separated by docket numbers in the input list of
    words.

    Parameters
    ----------
    dockets: List[Word]
        The list of dockets to separate and parse

    Yields
    ------
    docket_number: str
        The docket number
    county: str
        The name of the county
    docket: List[Word]
        The words for each docket
    """
    header_pattern = "(First Judicial District of Pennsylvania)|(.* County Court of Common Pleas)"

    # Delete any headers
    max_header_size = 5
    for pg in reversed(
        find_line_numbers(
            dockets,
            header_pattern,
            how="regex",
            missing="ignore",
        )
    ):
        # Loop over header row
        # REMOVE: any "Continued" lines of FJD / Court Summary header
        for i in reversed(range(0, max_header_size)):

            if pg + i < len(dockets) - 1:
                w = dockets[pg + i]

                if (
                    w.text == "Court Summary"
                    or re.match(header_pattern, w.text) is not None
                    or "Continued" in w.text
                ):
                    del dockets[pg + i]

    # Get docket numbers
    indices: List[Optional[int]] = []
    docket_numbers = []
    for i, w in enumerate(dockets):
        if w.text.startswith("MC-") or w.text.startswith("CP-"):
            indices.append(i)
            docket_numbers.append(w.text)

    # Add the ending slice index
    indices.append(None)

    # Yield the parts for each docket
    returned_dockets: List[str] = []
    for i in range(len(indices) - 1):

        # This docket number
        this_docket_num = docket_numbers[i]

        # Skip dockets we've already returned
        if this_docket_num in returned_dockets:
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
        returned_dockets.append(this_docket_num)
