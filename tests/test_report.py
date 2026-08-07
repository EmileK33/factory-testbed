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


def test_report_includes_a_tags_column_header():
    text = render_report()
    header = text.splitlines()[3]
    assert "tags" in header


def test_report_puts_each_records_tags_on_its_own_row():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    lines = text.splitlines()
    for row in accepted:
        row_line = next(candidate for candidate in lines if candidate.startswith(row["id"] + " "))
        assert row_line.rstrip().endswith(", ".join(row["tags"]))


def test_report_blanks_a_record_with_no_tags():
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    text = render_report(records=[record])
    lines = text.splitlines()
    row_line = next(candidate for candidate in lines if candidate.startswith("R-9001 "))
    assert row_line.rstrip().endswith("-")


def test_report_states_the_true_validated_vs_reported_field_counts():
    # Hardcoded, not derived from validate.VALIDATED_FIELDS /
    # report.REPORTED_FIELDS: id, name, amount, currency, region are checked
    # by check_record() (5); tags is reported but only normalised, not
    # checked (+1) = 6 reported fields total.
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()
