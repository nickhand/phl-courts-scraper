"""Define the schema for the court summary."""

from dataclasses import dataclass, fields
from typing import Any, Iterator, List, Optional, Union

import pandas as pd

from ..utils import DataclassBase

__all__ = ["CourtSummary", "Docket", "Charge", "Sentence"]


@dataclass
class Sentence(DataclassBase):
    """
    A Sentence object.

    Parameters
    ----------
    sentence_dt :
        the date of the sentence
    sentence_type :
        the sentence type
    program_period :
        the program period
    sentence_length :
        the length of the sentence
    """

    sentence_dt: str
    sentence_type: str
    program_period: Optional[str]
    sentence_length: Optional[str]

    def __post_init__(self):

        # Store the sentence date as a datetime
        self.sentence_dt = pd.to_datetime(self.sentence_dt)

    def __repr__(self):
        cls = self.__class__.__name__
        if not pd.isna(self.sentence_dt):
            dt = self.sentence_dt.strftime("%m/%d/%y")
            dt = f"'{dt}'"
        else:
            dt = "NaT"
        s = f"sentence_dt={dt}, sentence_type='{self.sentence_type}'"
        return f"{cls}({s})"


@dataclass
class Charge(DataclassBase):
    """
    A Charge object.

    Parameters
    ----------
    seq_no :
        the charge sequence number
    statute :
        the statute
    description : optional
        description of the statute
    grade : optional
        the grade, e.g., felony, misdemeanor, etc.
    disposition : optional
        the disposition for the charge, if present
    sentences : optional
        list of any sentences associated with the charge
    """

    seq_no: str
    statute: str
    description: Optional[str]
    grade: Optional[str]
    disposition: Optional[str]
    sentences: Optional[List[Sentence]]

    @property
    def meta(self):
        """A dict of the meta info associated with the charge"""

        exclude = ["sentences"]
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in exclude
        }

    def __iter__(self) -> Iterator[Sentence]:
        """Iterate through the sentences."""
        return iter(self.sentences)

    def __len__(self):
        """Return the length of the sentences."""
        return len(self.sentences)

    def __getitem__(self, index):
        """Index the sentences."""
        return self.sentences.__getitem__(index)

    def __repr__(self):
        cls = self.__class__.__name__

        cols = ["seq_no", "statute", "description"]
        s = ", ".join([f"{col}='{getattr(self, col)}'" for col in cols])
        s += f", num_sentences={len(self.sentences)}"
        return f"{cls}({s})"


@dataclass
class Docket(DataclassBase):
    """
    A Docket object.

    Parameters
    ----------
    docket_number :
        the docket number
    proc_status :
        the status of the docket proceedings
    dc_no :
        the DC incident number
    otn :
        the offense tracking number
    arrest_dt :
        the arrest date
    county :
        the PA county where case is being conducted
    status :
        the docket status as determined by the section on the court
        summary, e.g., "Active", "Closed", etc.
    extra :
        list of any additional header info for the docket
    psi_num : optional
        pre-sentence investigation number
    prob_num : optional
        the probation number
    disp_date : optional
        date of disposition
    disp_judge : optional
        the disposition judge
    def_atty : optional
        the name of the defense attorney
    trial_dt : optional
        the date of the trial
    legacy_no : optional
        the legacy number for the docket
    last_action : optional
        the last action in the case
    last_action_date : optional
        the date of the last action
    last_action_room : optional
        the room where last action occurred
    next_action : optional
        the next action to occur
    next_action_date : optional
        the date of the next action
    next_action_room : optional
        the room where next action will occur
    charges : optional
        a list of charges associated with this case
    """

    docket_number: str
    proc_status: str
    dc_no: str
    otn: str
    arrest_dt: str
    county: str
    status: str
    extra: List[Any]
    psi_num: Optional[str]
    prob_num: Optional[str]
    disp_date: Optional[str]
    disp_judge: Optional[str]
    def_atty: Optional[str]
    trial_dt: Optional[str]
    legacy_no: Optional[str]
    last_action: Optional[str]
    last_action_date: Optional[str]
    last_action_room: Optional[str]
    next_action: Optional[str]
    next_action_date: Optional[str]
    next_action_room: Optional[str]
    charges: Optional[List[Charge]]

    def __post_init__(self) -> None:

        # Convert columns to datetime objects
        for col in [
            "arrest_dt",
            "disp_date",
            "trial_dt",
            "last_action_date",
            "next_action_date",
        ]:
            value = getattr(self, col)
            if isinstance(value, str):
                setattr(self, col, pd.to_datetime(value))

    def to_pandas(self) -> pd.DataFrame:
        """
        Return a dataframe representation of the data,
        where each row represents a separate charge.
        """
        # Each row is a Docket
        out = pd.DataFrame([c.to_dict() for c in self])

        # Convert charge dicts to Charge objects
        out["sentences"] = out["sentences"].apply(
            lambda l: [Sentence(**v) for v in l]
        )
        return out

    @property
    def meta(self):
        """A dict of the meta info associated with the docket"""

        exclude = ["charges"]
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in exclude
        }

    def __getitem__(self, index):
        """Index the charges."""
        return self.charges.__getitem__(index)

    def __iter__(self) -> Iterator[Charge]:
        """Iterate through the charges."""
        return iter(self.charges)

    def __len__(self):
        """The number of charges."""
        return len(self.charges)

    def __repr__(self) -> str:
        cls = self.__class__.__name__

        if not pd.isna(self.arrest_dt):
            dt = self.arrest_dt.strftime("%m/%d/%y")
            dt = f"'{dt}'"
        else:
            dt = "NaT"

        s = [
            f"{self.docket_number}",
            str(self.status),
            f"arrest_dt={dt}",
            f"num_charges={len(self)}",
        ]
        return f"{cls}({', '.join(s)})"


@dataclass
class CourtSummary(DataclassBase):
    """A Court Summary object.

    Parameters
    ----------
    name :
        The name of the defendant.
    date_of_birth :
        The defendant's date of birth.
    eyes :
        The defendant's eye color.
    sex :
        The defendant's sex.
    hair :
        The defendant's hair color.
    race :
        The defendant's race.
    location :
        Defendant location
    aliases :
        List of aliases for the defendant
    dockets :
        List of Docket objects on the court summary
    """

    name: str
    date_of_birth: str
    eyes: str
    sex: str
    hair: str
    race: str
    location: str
    aliases: List[str]
    dockets: List[Docket]

    def to_pandas(self) -> pd.DataFrame:
        """
        Return a dataframe representation of the data,
        where each row represents a separate docket.
        """
        # Each row is a Docket
        out = pd.DataFrame([c.to_dict() for c in self])

        # Convert charge dicts to Charge objects
        out["charges"] = out["charges"].apply(
            lambda l: [Charge(**v) for v in l]
        )

        # Each row is a Docket
        return out

    @property
    def meta(self):
        """A dict of the meta info associated with the court summary."""

        exclude = ["dockets"]
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in exclude
        }

    def __iter__(self) -> Iterator[Docket]:
        """Yield the object's dockets."""
        return iter(self.dockets)

    def __len__(self) -> int:
        """Return the number of dockets."""
        return len(self.dockets)

    def __getitem__(self, index):
        """Index the dockets."""
        return self.dockets.__getitem__(index)

    def __repr__(self) -> str:
        """Shorten the default dataclass representation."""
        cls = self.__class__.__name__
        return f"{cls}(name='{self.name}', num_dockets={len(self)})"
