"""Utility functions and classes."""

from __future__ import annotations

import datetime
import itertools
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import desert
import marshmallow
import numpy as np
import pandas as pd
import pdfplumber
from intervaltree import IntervalTree
from selenium import webdriver


class TimeField(marshmallow.fields.DateTime):
    """Custom time field to handle string to datetime conversion."""

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore
        """Return string representation of datetime objects."""
        if not value:
            return ""
        if isinstance(value, datetime.datetime):
            assert self.format is not None
            return value.strftime(self.format)
        return super()._serialize(value, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore
        """Convert strings to datetime objects."""
        if value == "":
            return None
        if isinstance(value, datetime.datetime):
            return value

        return super()._deserialize(value, attr, data, **kwargs)


def convert_to_floats(
    df: pd.DataFrame,
    usecols: Optional[List[str]] = None,
    errors: str = "coerce",
) -> pd.DataFrame:
    """
    Convert string values in currency format to floats.

    Parameters
    ----------
    df: pd.DataFrame
        the data to format
    usecols: List[str]
        an optional list of columns to convert
    errors: str
        - If `raise`, then invalid parsing will raise an exception.
        - If `coerce`, then invalid parsing will be set as NaN.
        - If `ignore`, then invalid parsing will return the input.

    Returns
    -------
    df: pd.DataFrame
        The dataframe with the values converted to floats
    """
    if usecols is None:
        usecols = df.columns

    for col in usecols:
        df[col] = pd.to_numeric(
            df[col]
            .replace(r"[\$,)]", "", regex=True)
            .replace("[(]", "-", regex=True),
            errors=errors,
        )

    return df


@contextmanager
def downloaded_pdf(
    driver: webdriver.Chrome,
    pdf_url: str,
    tmpdir: str,
    interval: int = 1,
    time_limit: int = 7,
) -> Iterator[Path]:
    """
    Context manager to download a PDF to a local directory.

    Parameters
    ----------
    driver: webdriver.Chrome
        The webdriver to use to download the PDF
    pdf_url: str
        The URL to download the PDF from
    tmpdir: str
        The local (temporary) download folder
    interval: int
        The interval to wait between each download attempt
    time_limit: int
        The maximum time to wait to download the PDF

    Yields
    ------
    pdf_path: Path
        The path to the downloaded PDF

    Raises
    ------
    ValueError
        If the PDF cannot be downloaded within the time limit
    """
    # The download folder
    download_dir = Path(tmpdir)

    pdf_path = None
    try:
        # Get the PDF
        driver.get(pdf_url)

        # Initialize
        pdf_files = list(download_dir.glob("*.pdf"))
        total_sleep = 0
        while not len(pdf_files) and total_sleep <= time_limit:
            time.sleep(interval)
            total_sleep += interval
            pdf_files = list(download_dir.glob("*.pdf"))

        if len(pdf_files):
            pdf_path = pdf_files[0]
            yield pdf_path
        else:
            raise ValueError("PDF download failed")
    finally:

        # Remove the file after we are done!
        if pdf_path is not None and pdf_path.exists():
            pdf_path.unlink()


# Create a generic variable that can be 'Parent', or any subclass.
Word_T = TypeVar("Word_T", bound="Word")


@dataclass
class Word:
    """
    A word in the PDF with associated text and bounding box.

    Parameters
    ----------
    x0: float
        The starting horizontal coordinate
    x1: float
        The ending horizontal coordinate
    bottom: float
        The bottom vertical coordinate
    top: float
        The top vertical coordinate
    text: str
        The associated text
    """

    x0: float
    x1: float
    top: float
    bottom: float
    text: str

    @property
    def x(self) -> float:
        """Alias for `x0`."""
        return self.x0

    @property
    def y(self) -> float:
        """Alias for `tops`."""
        return self.top

    @classmethod
    def from_dict(cls: Type[Word_T], data: Dict[str, Any]) -> Word_T:
        """Initialize from a data dictionary."""
        schema = desert.schema(cls, meta={"unknown": marshmallow.EXCLUDE})
        return schema.load(data)


def find_phrases(words: List[Word], *keywords: str) -> Optional[List[Word]]:
    """
    Find a list of consecutive words that match the input keywords.

    Parameters
    ----------
    words: List[Word]
        The list of words to check
    keywords: str
        One or more keywords representing the phrase to search for

    Returns
    -------
    phrase: List[Word]
        If a match exists, return the matching words
    """
    # Make sure we have keywords
    assert len(keywords) > 0

    # Iterate through words and check
    for i, w in enumerate(words):

        # Matched the first word!
        if w.text == keywords[0]:

            # Did we match the rest
            match = True
            for j, keyword in enumerate(keywords[1:]):
                if keyword != words[i + 1 + j].text:
                    match = False

            # Match!
            if match:
                return words[i : i + len(keywords)]

    return None


def get_pdf_words(
    pdf_path: str,
    x_tolerance: int = 5,
    y_tolerance: int = 3,
    footer_cutoff: int = 0,
    header_cutoff: int = 0,
    keep_blank_chars: bool = False,
) -> List[Word]:
    """
    Parse a PDF into its words.

    This will return the parsed words as well as x/y locations.

    Parameters
    ----------
    pdf_path: str
        The path to the PDF to parse
    x_tolerance: int
        The x tolerance to use when extracting out words
    y_tolerance: int
        The y tolerance to use when extracting out words
    footer_cutoff: int
        The amount of page to ignore at the bottom of the page
    header_cutoff: int
        The amount of page to ignore at the top of the page
    keep_blank_chars: bool
        Whether to keep the blank characters when parsing words

    Returns
    -------
    List[Word]:
        The list of Word objects in the PDF
    """
    with pdfplumber.open(pdf_path) as pdf:

        # Loop over pages
        offset = 0
        words = []
        for i, pg in enumerate(pdf.pages):

            # Extract out words
            for word_dict in pg.extract_words(
                keep_blank_chars=keep_blank_chars,
                x_tolerance=x_tolerance,
                y_tolerance=y_tolerance,
            ):

                # Convert to a Word
                word = Word.from_dict(word_dict)

                # Check header and footer cutoffs
                if word.bottom < footer_cutoff and word.top > header_cutoff:

                    # Clean up text
                    word.text = word.text.strip()

                    # Add the offset
                    word.top += offset
                    word.bottom += offset

                    # Save it
                    words.append(word)

            # Effective height of this page
            effective_height = footer_cutoff - header_cutoff
            offset += effective_height

        # Sort the words top to bottom and left to right
        words = sorted(words, key=attrgetter("top", "x0"), reverse=False)

        return words


def to_snake_case(
    d: Dict[str, str], replace: List[str] = ["."]
) -> Dict[str, str]:
    """
    Format the keys of the input dictionary to be in snake case.

    Note
    ----
    This converts keys from "Snake Case" to "snake_case".

    Parameters
    ----------
    d: Dict[str, str]
        Contains the keys to convert
    replace: List[str]
        A list of characters to replace with blanks

    Returns
    -------
    Dict[str, str]
        The converted dictionary
    """

    def _format_key(key: str) -> str:
        for c in replace:
            key = key.replace(c, "")
        return key.lower()

    return {
        "_".join(_format_key(key).split()): value for key, value in d.items()
    }


def groupby(
    words: List[Word], key: str, sort: bool = False
) -> Iterator[Tuple[float, Iterator[Word]]]:
    """Group words by the specified attribute, optionally sorting."""
    if sort:
        words = sorted(words, key=attrgetter(key))
    return itertools.groupby(words, attrgetter(key))


def find_nearest(array: Iterable[float], value: float) -> int:
    """Return the index of nearest match."""
    a = np.asarray(array)
    idx = (np.abs(a - value)).argmin()
    return idx


def group_into_lines(
    words: List[Word], tolerance: int = 10
) -> Dict[float, List[Word]]:
    """Group words into lines, with a specified tolerance."""
    tree = IntervalTree()
    for i in range(len(words)):
        y = words[i].y
        tree[y - tolerance : y + tolerance] = words[i]  # type: ignore

    result: Dict[float, List[Word]] = {}
    for y in sorted(np.unique([w.y for w in words])):
        objs = [iv.data for iv in tree[y]]
        values = sorted(objs, key=attrgetter("x"))

        if values not in result.values():
            result[y] = values

    return result


# Create a generic variable that can be 'Parent', or any subclass.
T = TypeVar("T", bound="DataclassSchema")


class DataclassSchema:
    """Base class to handled serializing and deserializing dataclasses."""

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Initialize from a data dictionary."""
        schema = desert.schema(cls)
        return schema.load(data)

    @classmethod
    def from_json(cls: Type[T], path_or_json: Union[str, Path]) -> T:
        """Initialize from either a file path or a valid JSON string."""
        # Convert to Path() first to check
        _path = path_or_json
        if isinstance(_path, str):
            _path = Path(_path)
        assert isinstance(_path, Path)

        d = None
        try:  # catch file error too long
            if _path.exists():
                d = json.load(_path.open("r"))
        except OSError:
            pass
        finally:
            if d is None:
                d = json.loads(str(path_or_json))

        return cls.from_dict(d)

    def to_dict(self) -> Dict[str, Any]:
        """Return a data dictionary representation of the data."""
        schema = desert.schema(self.__class__)
        return schema.dump(self)

    def to_json(
        self, path: Optional[Union[str, Path]] = None
    ) -> Optional[str]:
        """
        Serialize the object to JSON.

        This will return either a valid JSON string or save the
        JSON string to the input file path.

        Parameters
        ----------
        path: Optional[Union[str, Path]]
            The (optional) file path to save the JSON encoding to

        Returns
        -------
        Optional[str]:
            The JSON string representation of the object
        """
        # Dump to a dictionary
        schema = desert.schema(self.__class__)
        d = schema.dump(self)

        if path is None:
            return json.dumps(d)
        else:
            if isinstance(path, str):
                path = Path(path)
            json.dump(
                d,
                path.open("w"),
            )

            return None
