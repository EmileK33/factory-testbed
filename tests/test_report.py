"""Tests for the rendered settlement report."""

from src.records import load_records
from src.report import render_report
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


def test_report_includes_the_tags_column_header():
    header = render_report().splitlines()[3]
    assert "tags" in header.split()


def test_report_puts_each_accepted_records_tags_on_its_row():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    for row in accepted:
        row_line = next(line for line in text.splitlines() if line.startswith(row["id"]))
        assert row_line.rstrip().endswith(", ".join(row["tags"]))


def test_report_shows_a_dash_for_a_record_with_no_tags():
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    text = render_report(records=[record])
    row_line = next(line for line in text.splitlines() if line.startswith("R-9001"))
    assert row_line.rstrip().endswith("-")


def test_report_reports_accurate_validation_coverage():
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()
