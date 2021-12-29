"""Define the schema for the court summary report."""


from dataclasses import dataclass, field, fields
from typing import Any, Dict, Iterator, List, Optional

import desert
import pandas as pd

from ..utils import DataclassSchema, TimeField


@dataclass
class Sentence(DataclassSchema):
    """
    A Sentence object.

    Parameters
    ----------
    sentence_type: str
        The sentence type
    sentence_dt: str
        The date of the sentence
    program_period: str, optional
        The program period
    sentence_length: str, optional
        The length of the sentence
    """

    sentence_type: str
    sentence_dt: str = desert.field(
        TimeField(format="%m/%d/%Y", allow_none=True)
    )  # type: ignore
    program_period: str = ""
    sentence_length: str = ""

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        cls = self.__class__.__name__
        if not pd.isna(self.sentence_dt):
            dt = self.sentence_dt.strftime("%m/%d/%y")  # type: ignore
            dt = f"'{dt}'"
        else:
            dt = "NaT"
        s = f"sentence_dt={dt}, sentence_type='{self.sentence_type}'"
        return f"{cls}({s})"


@dataclass
class Charge(DataclassSchema):
    """
    A Charge object.

    Parameters
    ----------
    seq_no: int
        the charge sequence number
    statute: str
        the statute
    description: str, optional
        description of the statute
    grade: str, optional
        the grade, e.g., felony, misdemeanor, etc.
    disposition: str, optional
        the disposition for the charge, if present
    sentences: List[Sentence], optional
        list of any sentences associated with the charge
    """

    seq_no: str
    statute: str
    description: str = ""
    grade: str = ""
    disposition: str = ""
    sentences: List[Sentence] = field(default_factory=list)

    @property
    def meta(self) -> Dict[str, Any]:
        """Return the meta information associated with the charge."""
        exclude = ["sentences"]
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in exclude
        }

    def __iter__(self) -> Iterator[Sentence]:
        """Iterate through the sentences."""
        return iter(self.sentences)

    def __len__(self) -> int:
        """Return the length of the sentences."""
        return len(self.sentences)

    def __getitem__(self, index: int) -> Sentence:
        """Index the sentences."""
        return self.sentences.__getitem__(index)

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        cls = self.__class__.__name__

        cols = ["seq_no", "statute", "description"]
        s = ", ".join([f"{col}='{getattr(self, col)}'" for col in cols])
        s += f", num_sentences={len(self.sentences)}"
        return f"{cls}({s})"


@dataclass
class Docket(DataclassSchema):
    """
    A Docket object.

    Parameters
    ----------
    docket_number: str
        The docket number
    proc_status: str
        The status of the docket proceedings
    dc_no: str
        The DC incident number
    otn: str
        The offense tracking number
    county: str
        The PA county where case is being conducted
    status: str
        The docket status as determined by the section on the court
        summary, e.g., "Active", "Closed", etc.
    extra: List[Any]
        List of any additional header information
    arrest_dt: str
        The arrest date
    psi_num: str, optional
        Pre-sentence investigation number
    prob_num: str, optional
        The probation number
    disp_date: str, optional
        The date of disposition
    disp_judge: str, optional
        The disposition judge
    def_atty: str, optional
        The name of the defense attorney
    legacy_no: str, optional
        The legacy number for the docket
    last_action: str, optional
        The last action in the case
    last_action_room: str, optional
        The room where last action occurred
    next_action: str, optional
        The next action to occur
    next_action_room: str, optional
        The room where next action will occur
    next_action_date: str, optional
        The date of the next action
    trial_dt: str, optional
        The date of the trial
    last_action_date: str, optional
        The date of the last action
    charges: str, optional
        A list of charges associated with this case
    """

    docket_number: str
    proc_status: str
    dc_no: str
    otn: str
    county: str
    status: str
    extra: List[Any]
    arrest_dt: str = desert.field(
        TimeField(format="%m/%d/%Y", allow_none=True)
    )  # type: ignore
    psi_num: str = ""
    prob_num: str = ""
    disp_judge: str = ""
    def_atty: str = ""
    legacy_no: str = ""
    last_action: str = ""
    last_action_room: str = ""
    next_action: str = ""
    next_action_room: str = ""
    next_action_date: Optional[str] = desert.field(
        TimeField(format="%m/%d/%Y", allow_none=True), default=""
    )  # type: ignore
    last_action_date: Optional[str] = desert.field(
        TimeField(format="%m/%d/%Y", allow_none=True), default=""
    )  # type: ignore
    trial_dt: Optional[str] = desert.field(
        TimeField(format="%m/%d/%Y", allow_none=True), default=""
    )  # type: ignore
    disp_date: Optional[str] = desert.field(
        TimeField(format="%m/%d/%Y", allow_none=True), default=""
    )  # type: ignore
    charges: List[Charge] = field(default_factory=list)

    def to_pandas(self) -> pd.DataFrame:
        """Return a dataframe representation of the data."""
        # Each row is a Charge
        out = pd.DataFrame([c.to_dict() for c in self])

        # Convert sentences dicts to Sentence objects
        out["sentences"] = out["sentences"].apply(
            lambda l: [Sentence(**v) for v in l]
        )
        return out

    @property
    def meta(self) -> Dict[str, Any]:
        """Return the meta information associated with the docket."""
        exclude = ["charges"]
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in exclude
        }

    def __getitem__(self, index: int) -> Charge:
        """Index the charges."""
        return self.charges.__getitem__(index)

    def __iter__(self) -> Iterator[Charge]:
        """Iterate through the charges."""
        return iter(self.charges)

    def __len__(self) -> int:
        """Return the number of charges."""
        return len(self.charges)

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        cls = self.__class__.__name__

        if not pd.isna(self.arrest_dt):
            dt = self.arrest_dt.strftime("%m/%d/%y")  # type: ignore
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
class CourtSummary(DataclassSchema):
    """
    A Court Summary object.

    Parameters
    ----------
    name: str
        The name of the defendant.
    date_of_birth: str
        The defendant's date of birth.
    eyes: str
        The defendant's eye color.
    sex: str
        The defendant's sex.
    hair: str
        The defendant's hair color.
    race: str
        The defendant's race.
    location: str
        Defendant location
    aliases: List[str]
        List of aliases for the defendant
    dockets: List[Docket]
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
        """Return the dataframe representation of the data."""
        # Each row is a Docket
        out = pd.DataFrame([c.to_dict() for c in self])

        # Convert charge dicts to Charge objects
        out["charges"] = out["charges"].apply(
            lambda l: [Charge(**v) for v in l]
        )

        # Each row is a Docket
        return out

    @property
    def meta(self) -> Dict[str, Any]:
        """Return the meta info associated with the court summary."""
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

    def __getitem__(self, index: int) -> Docket:
        """Index the dockets."""
        return self.dockets.__getitem__(index)

    def __repr__(self) -> str:
        """Shorten the default dataclass representation."""
        cls = self.__class__.__name__
        return f"{cls}(name='{self.name}', num_dockets={len(self)})"
