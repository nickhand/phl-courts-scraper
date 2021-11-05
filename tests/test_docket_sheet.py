from pathlib import Path

import pytest
from phl_courts_scraper.docket_sheet import DocketSheetParser, DocketSheetResults

current_dir = Path(__file__).parent.absolute()


@pytest.fixture
def parser():
    """Return a `DocketSheetParser` to use in multiple tests."""
    return DocketSheetParser()


def _test_report(report):

    # Serialize / de-serialize
    report2 = DocketSheetResults.from_json(report.to_json())
    assert report.to_dict() == report2.to_dict()


def test_docket_sheet_1():
    """Test example #1 of docket sheet report."""
    report = parser(current_dir / "data" / "DocketSheetReport1.pdf", section="bail")
    _test_report(report)


def test_docket_sheet_2():
    """Test example #2 of docket sheet report."""
    report = parser(current_dir / "data" / "DocketSheetReport2.pdf", section="bail")
    _test_report(report)


def test_docket_sheet_3():
    """Test example #3 of docket sheet report."""
    report = parser(current_dir / "data" / "DocketSheetReport3.pdf", section="bail")
    _test_report(report)
