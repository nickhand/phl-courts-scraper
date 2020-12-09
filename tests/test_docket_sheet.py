from pathlib import Path

from phl_courts_scraper.docket_sheet import DocketSheetParser

current_dir = Path(__file__).parent.absolute()


def _test_report(report):

    cols = [
        "Bail Action",
        "Date",
        "Bail Type",
        "Percentage",
        "Amount",
        "Bail Posting Status",
        "Posting Date",
    ]
    assert all(col in cols for col in report.columns)


def test_court_summary_1():
    """Test example #1 of docket sheet report."""

    # Initialize
    parser = DocketSheetParser(current_dir / "data" / "DocketSheetReport1.pdf")
    report = parser()
    _test_report(report)


def test_court_summary_2():
    """Test example #2 of docket sheet report."""

    # Initialize
    parser = DocketSheetParser(current_dir / "data" / "DocketSheetReport2.pdf")
    report = parser()
    _test_report(report)
