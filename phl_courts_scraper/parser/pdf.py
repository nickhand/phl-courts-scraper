from dataclasses import dataclass
from operator import itemgetter
from typing import List

import pdfplumber


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
        a list of tuples containing x/y position and parsed line string
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
