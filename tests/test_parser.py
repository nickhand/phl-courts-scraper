from pathlib import Path

from phl_courts_scraper.parser import CourtSummary

current_dir = Path(__file__).parent.absolute()


def test_court_summary_1():
    """Test example #1 of court summary report."""

    # Initialize
    report = CourtSummary(current_dir / "data" / "CourtSummaryReport1.pdf")

    # Serialize / de-serialize
    report2 = CourtSummary.from_json(report.to_json())

    assert report == report2


def test_court_summary_2():
    """Test example #2 of court summary report."""

    # Initialize
    report = CourtSummary(current_dir / "data" / "CourtSummaryReport2.pdf")

    # Serialize / de-serialize
    report2 = CourtSummary.from_json(report.to_json())

    assert report == report2
