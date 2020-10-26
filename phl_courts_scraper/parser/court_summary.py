from __future__ import annotations

import collections
import json
from dataclasses import dataclass
from operator import attrgetter, itemgetter
from pathlib import Path
from typing import ClassVar, List, Optional, Tuple, Union

import numpy as np

from .pdf import Word, get_pdf_words
from .utils import find_nearest, format_dict_keys, group_into_lines, groupby

__all__ = ["CourtSummary"]


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
            if line[0].text.isdigit():

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
                        else:
                            raise ValueError(
                                "Error parsing docket lines — this should never happen!"
                            )

            if i == len(lines_y) - 1:
                results.append(row)

    # Format the string keys in header
    header_info = format_dict_keys(header_info)
    header_info["extra"] = extra

    # Format the string keys in results
    results = [format_dict_keys(r) for r in results]
    for r in results:
        r["sentences"] = [format_dict_keys(d) for d in r["sentences"]]

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
    Yield words associated with all of the dockets
    of a specific kind, either "Active" or "Closed".

    Parameters
    ----------
    words :
        the list of words to parse
    kind :
        either "Active" or "Closed"

    Yields
    ------
    docket :
        the words for each docket
    """
    # Delete any headers
    header_size = 5
    for pg in reversed(
        _find_line_numbers(
            dockets,
            "First Judicial District of Pennsylvania",
            return_all=True,
            missing="ignore",
        )
    ):
        del dockets[pg : pg + header_size]

    # Get docket numbers
    docket_info = [
        (i, w.text)
        for i, w in enumerate(dockets)
        if w.text.startswith("MC-") or w.text.startswith("CP-")
    ]

    indices, docket_numbers = list(zip(*docket_info))

    indices = list(indices) + [None]
    counties = []

    for i in range(len(indices) - 1):

        #
        prev_word = dockets[indices[i] - 1]
        first_word = dockets[indices[i]]

        if _vertically_aligned(
            prev_word.x, first_word.x, tol=0.5
        ) and _horizontally_aligned(prev_word.y, first_word.y, tol=15):
            counties.append(prev_word.text)
            indices[i] = indices[i] - 1
        else:
            counties.append(counties[-1])

    # Yield the parts for each docket
    returned = []
    for i in range(len(indices) - 1):

        # This docket number
        this_docket_num = docket_numbers[i]

        # Skip dockets we've alreay returned
        if this_docket_num in returned:
            continue

        # Determine the index of when the next one starts
        j = i + 1
        while j < len(docket_numbers) and this_docket_num == docket_numbers[j]:
            j += 1

        start = indices[i]
        stop = indices[j]

        # Return
        yield this_docket_num, counties[i], dockets[start:stop]

        # Track which ones we've returned
        returned.append(this_docket_num)


@dataclass
class CourtSummary:
    """Parser for Court Summary Reports."""

    path: Union[str, Path]
    SECTION_HEADERS: ClassVar[List[str]] = [
        "Active",
        "Closed",
        "Inactive",
        "Archived",
        "Adjudicated",
    ]

    def __post_init__(self):
        """Parse and save the input PDF."""

        # Store path as str
        self.path = str(self.path)

        # Parse PDF
        self.words = get_pdf_words(self.path)

        # Determine section headers
        starts = {}
        for hdr in self.SECTION_HEADERS:
            line = _find_line_numbers(self.words, hdr, missing="ignore")
            if line != []:
                starts[hdr] = line

        # Put it in the correct order (ascending)
        sections = sorted(starts, key=itemgetter(1))
        sorted_starts = collections.OrderedDict()
        for key in sections:
            sorted_starts[key] = starts[key]

        # Parse the dockets
        self.dockets = collections.OrderedDict()
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
            words_this_section = self.words[
                this_section_start:next_section_start
            ]

            dockets = {}
            for docket_number, county, docket in _yield_dockets(
                words_this_section
            ):

                # Do the parsing work
                info = _parse_raw_docket(docket_number, docket)

                # Store the county
                info["header"]["county"] = county

                if docket_number not in dockets:
                    dockets[docket_number] = info
                else:
                    dockets[docket_number]["header"].update(info["header"])
                    dockets[docket_number]["charges"] += info["charges"]

            self.dockets[this_section] = dockets

    def __getitem__(self, key):
        if key not in self.sections:
            raise KeyError(f"No such section '{key}'")
        return self.dockets[key]

    @property
    def sections(self):
        """Sections in the court summary report."""
        return list(self.dockets)

    @property
    def header(self) -> dict:
        """The header of the court summary."""
        return _parse_header(self.words, self.sections[0])

    def asdict(self, slim: bool = False):
        """Convert the class to a dictionary."""

        out = {}
        for key in ["path", "header", "dockets"]:
            out[key] = getattr(self, key)

        if not slim:
            out["words"] = [word.__dict__ for word in self.words]

        return out

    def to_json(
        self, path: Optional[Union[Path, str]] = None, slim: bool = False
    ) -> Optional[str]:
        """Convert to json representation."""

        if path:
            if isinstance(path, str):
                path = Path(path)

            with path.open("w") as fp:
                json.dump(self.asdict(slim=slim), fp)

        else:
            return json.dumps(self.asdict(slim=slim))

    @classmethod
    def from_json(cls, path: Union[Path, str]) -> CourtSummary:
        """Load data from a json file."""

        if isinstance(path, str):
            # Try to load as json first
            try:
                d = json.loads(path)
            except Exception:
                if Path(path).exists():
                    d = json.load(path.open("r"))
                else:
                    raise ValueError(
                        "Unable to interpret input string as path or valid json string."
                    )
        else:
            d = json.load(path.open("r"))

        # Convert words to objects
        if "words" in d:
            d["words"] = [Word(**word) for word in d["words"]]
        else:
            d["words"] = None

        # Initialize
        out = cls(path=d.pop("path"))

        # Add other attributes
        for key in ["words", "header", "dockets"]:
            out.__dict__[key] = d[key]

        return out
