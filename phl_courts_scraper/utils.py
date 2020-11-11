"""Utility functions and classes."""

from __future__ import annotations

import datetime
import itertools
import json
from dataclasses import dataclass
from operator import attrgetter, itemgetter
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
import numpy as np
import pandas as pd
import pdfplumber
from intervaltree import IntervalTree


@dataclass
class Word:
    """A word in the PDF, storing text and x/y coordinates."""

    x: float
    y: float
    text: str


def get_pdf_words(pdf_path: str, x_tolerance: int = 5) -> List[Word]:
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
    FOOTER_CUTOFF = 640
    out = []

    with pdfplumber.open(pdf_path) as pdf:

        # Loop over pages
        for i, pg in enumerate(pdf.pages):

            # Extract out words
            words = pg.extract_words(
                keep_blank_chars=True, x_tolerance=x_tolerance
            )
            words = [
                word for word in words if float(word["top"]) < FOOTER_CUTOFF
            ]

            # Texts
            texts = [word["text"].strip() for word in words]
            x0 = [float(word["x0"]) for word in words]
            top = [float(word["top"]) + i * FOOTER_CUTOFF for word in words]

            # Sort
            X = list(zip(x0, top, texts))
            Y = sorted(X, key=itemgetter(1, 0), reverse=False)
            out.append(Y)

    return [Word(*tup) for pg in out for tup in pg]


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


def find_nearest(array: Iterable, value: str) -> int:
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

        if path is None:
            return json.dumps(self.to_dict())
        else:
            if isinstance(path, str):
                path = Path(path)
            json.dump(
                self.to_dict(), path.open("w"),
            )

            return None
