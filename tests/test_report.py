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


def test_report_shows_the_tags_column_header():
    header_line = render_report().splitlines()[3]
    assert header_line == "id      name            region  amount  currency  tags"


def test_report_shows_each_accepted_records_tags():
    text = render_report()
    # R-1001's feed row is 'eu,"high,priority",settled'. parse_tags() splits on
    # every comma regardless of the quoting (a separately-flagged quirk, out of
    # scope here — see src/parse.py), so today it yields four tags, not three;
    # this test pins the report's join of whatever parse_tags() returns, not a
    # claim about parse_tags()'s own correctness.
    assert "eu, high, priority, settled" in text
    assert "na, settled" in text  # R-1002


def test_report_renders_a_dash_for_a_record_with_no_tags():
    records = [
        {
            "id": "R-9001",
            "name": "No Tags Co",
            "amount": 100,
            "currency": "USD",
            "region": "NA",
            "tags": "",
        }
    ]
    text = render_report(records)
    row = next(line for line in text.splitlines() if line.startswith("R-9001"))
    assert row.split()[-1] == "-"
    assert "[]" not in text
    assert "['']" not in text


def test_report_states_how_many_reported_fields_are_validated():
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()
