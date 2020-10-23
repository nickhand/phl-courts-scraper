from __future__ import annotations

import collections
import json
from dataclasses import dataclass
from operator import attrgetter, itemgetter
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np

from .pdf import Word, get_pdf_words
from .utils import find_nearest, format_dict_keys, group_into_lines, groupby

__all__ = ["CourtSummary"]


def _parse_raw_docket(words: List[Word]) -> Tuple[str, dict]:
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
    unique_header_lines = []
    for elem in header_lines:
        if elem not in unique_header_lines:
            unique_header_lines.append(elem)

    unique_header_nrows = len(unique_header_lines)
    multiline_header = unique_header_nrows > 1

    # Split into docket header and body
    docket_header, docket_body = _parse_docket_header(words)

    # First two lines are the county and docket number
    county = docket_header[0].text
    docket_number = docket_header[1].text

    # Format the rest
    header_info = dict(
        [[s.strip() for s in w.text.split(":")] for w in docket_header[2:]]
    )

    # Parse the docket body
    results = []
    if len(docket_body):

        # Group into lines
        lines = group_into_lines(docket_body, tolerance=3)
        lines_y = sorted(lines)  # the y-values (keys of lines)

        # Determine indents of rows
        indents = collections.OrderedDict()
        for y in lines_y:

            # If this line is a header line, skip it!
            if lines[y] in header_lines:
                continue

            # First x value in line
            start = lines[y][0].x

            # indented?
            if abs(start - lines[lines_y[0]][0].x) < 5:
                indented = False
            elif multiline_header and abs(start - lines[lines_y[1]][0].x) < 5:
                indented = True
            else:
                indented = None

            if indented is not None:
                indents[y] = indented
            else:
                if len(indents):
                    lines[list(indents)[-1]] += lines.pop(y)
                else:
                    raise ValueError("This should never happen!")

        # Combine rows that span multiple lines
        for y in lines:
            line = lines[y]
            c = collections.Counter([w.x for w in line])
            c = collections.Counter(el for el in c.elements() if c[el] > 1)
            if len(c):
                x0 = list(c.elements())[0]
                to_merge = sorted(
                    [w for w in line if w.x == x0], key=attrgetter("y"),
                )
                t = " ".join([w.text for w in to_merge])
                new_word = Word(to_merge[0].x, to_merge[0].y, t)
                new_line = [w for w in line if w.x != x0] + [new_word]
                lines[y] = new_line

        # Finally parse together lines into a dict
        row = None
        for i, y in enumerate(indents):
            indented = indents[y]
            if not indented:
                if row is not None:
                    results.append(row)
                row = {}
                row["Sentences"] = []
                header = unique_header_lines[0]
            else:
                header = unique_header_lines[1]

            header_x0 = [w.x for w in header]
            header_values = [w.text for w in header]
            line = lines[y]

            if indented:
                r = {}
            else:
                r = row

            for iline in range(len(line)):
                w = line[iline]
                nearest = find_nearest(header_x0, w.x)
                r[header_values[nearest]] = w.text

            if indented:
                row["Sentences"].append(r)

            if i == len(indents) - 1:
                results.append(row)

    # Format the string keys in header
    header_info = format_dict_keys(header_info)
    header_info["county"] = county

    # Format the string keys in results
    results = [format_dict_keys(r) for r in results]
    for r in results:
        r["sentences"] = [format_dict_keys(d) for d in r["sentences"]]

    return docket_number, {"header": header_info, "charges": results}


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


def _parse_docket_header(words: List[Word]) -> Tuple[List[Word], List[Word]]:
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

    grouped = [list(group) for _, group in groupby(words, "y")]
    grouped = [item for sublist in grouped for item in sublist]
    i = _find_line_numbers(grouped, "Seq No", missing="ignore")
    if i == []:
        return grouped, []
    else:
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

    # Find the docket numbers
    docket_numbers = [
        w.text
        for w in dockets
        if w.text.startswith("MC") or w.text.startswith("CP")
    ]

    # Find the indices of the docket numbers
    indices = [
        _find_line_numbers(dockets, docket_number) - 1
        for docket_number in docket_numbers
    ] + [None]

    # Yield the parts for each docket
    for i in range(len(indices) - 1):
        yield dockets[indices[i] : indices[i + 1]]


@dataclass
class CourtSummary:
    """Parser for Court Summary Reports."""

    path: Union[str, Path]

    def __post_init__(self):
        """Parse and save the input PDF."""

        # Store path as str
        self.path = str(self.path)

        # Parse PDF
        self.words = get_pdf_words(self.path)

        # Determine section headers
        starts = {}
        for hdr in ["Active", "Closed", "Inactive", "Archived"]:
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
            for docket in _yield_dockets(words_this_section):
                docket_number, info = _parse_raw_docket(docket)
                dockets[docket_number] = info

            self.dockets[this_section] = dockets

    @property
    def sections(self):
        """Sections in the court summary report."""
        return list(self.dockets)

    @property
    def header(self) -> dict:
        """The header of the court summary."""
        return _parse_header(self.words, self.sections[0])

    @property
    def active_dockets(self) -> dict:
        """The active dockets."""
        return self.dockets.get("Active", {})

    @property
    def closed_dockets(self) -> dict:
        """The closed dockets."""
        return self.dockets.get("Closed", {})

    @property
    def inactive_dockets(self) -> dict:
        """The inactive dockets."""
        return self.dockets.get("Inactive", {})

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
