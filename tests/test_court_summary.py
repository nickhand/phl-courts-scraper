from pathlib import Path

from phl_courts_scraper.court_summary import CourtSummary, CourtSummaryParser

current_dir = Path(__file__).parent.absolute()


def _test_report(report):

    # Verify details
    assert len(report) == len(report.dockets)
    if len(report):
        assert report[0] == report.dockets[0]

    # Loop over dockets and check length
    for docket in report:
        assert len(docket) == len(docket.charges)
        if len(docket):
            assert docket[0] == docket.charges[0]

        # Loop over charges and check length
        for charge in docket:
            assert len(charge) == len(charge.sentences)
            if len(charge):
                assert charge[0] == charge.sentences[0]

    # Serialize / de-serialize
    report2 = CourtSummary.from_json(report.to_json())
    assert report.to_dict() == report2.to_dict()


def test_court_summary_1():
    """Test example #1 of court summary report."""

    # Initialize
    parser = CourtSummaryParser(
        current_dir / "data" / "CourtSummaryReport1.pdf"
    )
    report = parser()
    _test_report(report)


def test_court_summary_2():
    """Test example #2 of court summary report."""

    # Initialize
    parser = CourtSummaryParser(
        current_dir / "data" / "CourtSummaryReport2.pdf"
    )
    report = parser()
    _test_report(report)
