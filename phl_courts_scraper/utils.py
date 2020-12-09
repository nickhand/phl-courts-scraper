"""Utility functions and classes."""

from __future__ import annotations

import datetime
import itertools
import json
from dataclasses import asdict, dataclass
from operator import attrgetter
from pathlib import Path
from typing import (
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
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

# Create a generic variable that can be 'Parent', or any subclass.
Word_T = TypeVar("Word_T", bound="Word")


@dataclass
class Word:
    """
    A word in the PDF with associated text and bounding box.

    Parameters
    ----------
    x0 :
        the starting horizontal coordinate
    x1 :
        the ending horizontal coordinate
    bottom :
        the bottom vertical coordinate
    top :
        the top vertical coordinate
    text :
        the associated text
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
    def from_dict(cls: Type[Word_T], data: dict) -> Word_T:
        """
        Return a new class instance from a dictionary
        representation.

        Parameters
        ----------
        data :
            The dictionary representation of the class.
        """
        schema = desert.schema(cls, meta={"unknown": marshmallow.EXCLUDE})
        return schema.load(data)


def find_phrases(words: List[Word], *keywords: str) -> Optional[List[Word]]:
    """
    Find a list of consecutive words that match the input keywords.

    Parameters
    ----------
    words :
        the list of words to check
    *keywords
        one or more keywords representing the phrase to search for
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
    """Parse a PDF and return the parsed words as well as x/y
    locations.

    Parameters
    ----------
    pdf_path :
        the path to the PDF to parse
    x_tolerance : optional
        the tolerance to use when extracting out words

    Returns
    -------
    words :
        a list of Word objects in the PDF
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


def to_snake_case(d: dict, replace: List[str] = ["."]) -> dict:
    """Format the keys of the input dictionary to be in snake case.

    This converts keys from "Snake Case" to "snake_case".
    """

    def _format_key(key):
        for c in replace:
            key = key.replace(c, "")
        return key.lower()

    return {
        "_".join(_format_key(key).split()): value for key, value in d.items()
    }


def groupby(words: List[Word], key: str, sort: bool = False) -> Iterator:
    """Group words by the specified attribute, optionally sorting."""
    if sort:
        words = sorted(words, key=attrgetter(key))
    return itertools.groupby(words, attrgetter(key))


def find_nearest(array: Iterable, value: float) -> int:
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
    def from_dict(cls: Type[T], data: dict) -> T:
        """
        Return a new class instance from a dictionary
        representation.

        Parameters
        ----------
        data :
            The dictionary representation of the class.
        """
        schema = desert.schema(cls)
        return schema.load(data)

    @classmethod
    def from_json(cls: Type[T], path_or_json: Union[str, Path]) -> T:
        """
        Return a new class instance from either a file path
        or a valid JSON string.

        Parameters
        ----------
        path_or_json :
            Either the path of the file to load or a valid JSON string.
        """

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

    def to_dict(self) -> dict:
        """Return a dictionary representation of the data."""
        schema = desert.schema(self.__class__)
        return schema.dump(self)

    def to_json(
        self, path: Optional[Union[str, Path]] = None
    ) -> Optional[str]:
        """
        Serialize the object to JSON, either returning a valid JSON
        string or saving to the input file path.

        Parameters
        ----------
        path :
            the file path to save the JSON encoding to
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
                d, path.open("w"),
            )

            return None
