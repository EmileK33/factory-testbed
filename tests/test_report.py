"""Tests for the rendered settlement report."""

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


def test_report_shows_the_tags_column_header():
    assert "tags" in REPORTED_FIELDS
    header_line = render_report().splitlines()[3]
    assert "tags" in header_line


def test_report_shows_each_accepted_records_tags():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    for row in accepted:
        joined = ", ".join(row["tags"])
        assert joined in text


def test_report_renders_an_empty_tag_list_as_a_dash():
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[record])
    row_line = [line for line in text.splitlines() if line.startswith("R-9001")][0]
    assert row_line.split()[-1] == "-"


def test_report_states_how_many_reported_fields_are_validated():
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()
