import itertools
from operator import attrgetter
from typing import Dict, Iterable, Iterator, List

import numpy as np
from intervaltree import IntervalTree

from .pdf import Word


def format_dict_keys(d, replace=["."]):
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
) -> Dict[int, List[Word]]:
    """Group words into lines, with a specified tolerance."""
    tree = IntervalTree()
    for i in range(len(words)):
        y = words[i].y
        tree[y - tolerance : y + tolerance] = words[i]

    result = {}
    for y in sorted(np.unique([w.y for w in words])):
        objs = [iv.data for iv in tree[y]]
        values = sorted(objs, key=attrgetter("x"))

        if values not in result.values():
            result[y] = values

    return result
