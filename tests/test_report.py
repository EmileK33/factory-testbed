"""Tests for the rendered settlement report."""

from src import validate
from src.records import load_records
from src.report import REPORTED_FIELDS, render_report
from src.validate import check_record


def test_report_lists_every_accepted_record():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    for row in accepted:
        assert row["id"] in text


def test_report_reports_the_counts_it_read():
    text = render_report()
    assert f"Records read: {len(load_records())}" in text


def test_report_ends_with_a_newline():
    assert render_report().endswith("\n")


def test_report_names_the_unlabelled_record():
    assert "Unlabelled records: Fennel Labs" in render_report()


def test_report_header_includes_tags_column():
    header_line = render_report().splitlines()[3]
    assert "tags" in header_line


def test_report_shows_each_accepted_records_tags():
    # R-1001's raw tags column is 'eu,"high,priority",settled'; parse_tags()
    # splits it into ["eu", "high", "priority", "settled"], and the report
    # joins that list with ", " for display.
    assert "eu, high, priority, settled" in render_report()


def test_report_renders_missing_tags_as_a_dash():
    raw = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[raw])
    row_line = next(line for line in text.splitlines() if line.startswith("R-9001"))
    assert row_line.rstrip().endswith("-")


def test_report_states_the_validated_field_count_accurately():
    expected = (
        f"{len(validate.VALIDATED_FIELDS)} of {len(REPORTED_FIELDS)} reported fields "
        "are checked by the validation rules."
    )
    assert expected in render_report()
