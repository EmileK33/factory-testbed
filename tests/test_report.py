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


def test_report_shows_each_records_tags():
    # R-1002's tags column in data/records.json is "na,settled", with no quoting
    # to worry about; the expected string is a literal here rather than
    # something produced by calling parse_tags()/check_record(), so this test
    # cannot be fooled by a shared bug in the code path it's checking.
    assert "na, settled" in render_report()


def test_report_tags_column_is_blank_for_no_tags():
    # A record with no "tags" key at all normalises to an empty list via
    # check_record() -> parse_tags(""). The report must show that as "-",
    # like every other blank cell, not as "[]" or an empty gap.
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[record])
    assert "USD       -" in text


def test_report_does_not_claim_all_fields_are_checked():
    # tags is reported but not one of validate.VALIDATED_FIELDS, so a report
    # that names 6 reported fields can no longer truthfully say "all reported
    # fields are checked by the validation rules." The fix is to not make that
    # claim at all (checked here), not to reword it into a different one.
    text = render_report()
    assert "reported fields are checked by the validation rules" not in text
    assert "Validation covers: id, name, amount, currency, region" in text
