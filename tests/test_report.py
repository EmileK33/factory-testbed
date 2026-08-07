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
    # R-1001's raw tags column is 'eu,"high,priority",settled': 3 tags, the
    # middle one containing a comma the upstream exporter quoted. parse_tags()
    # respects that quoting -> ["eu", "high,priority", "settled"], and the
    # report joins that list with ", " for display.
    assert "eu, high,priority, settled" in render_report()


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
    # Pinned as a literal string rather than re-derived from REPORTED_FIELDS /
    # VALIDATED_FIELDS: re-deriving the same formula the implementation uses
    # would pass even if that formula stopped counting a real intersection
    # (e.g. reverted to two independent lengths compared side by side).
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()


def test_report_counts_only_fields_that_are_both_reported_and_validated():
    # tags is reported but not validated, so it must not count toward the
    # "checked" total even though REPORTED_FIELDS and VALIDATED_FIELDS are
    # each individually non-empty.
    assert "tags" not in validate.VALIDATED_FIELDS
    assert "tags" in REPORTED_FIELDS


def test_report_checked_count_is_a_real_intersection_not_two_lengths(monkeypatch):
    # With today's data VALIDATED_FIELDS is a strict subset of REPORTED_FIELDS,
    # so "count the intersection" and "just print len(VALIDATED_FIELDS) next to
    # len(REPORTED_FIELDS)" produce the same number and this test would not
    # tell them apart. Patch in a validated field that ISN'T reported to force
    # the two approaches to diverge: a real intersection must still count only
    # the 2 fields ("id", "name") that are in both tuples, not len(VALIDATED_FIELDS)
    # (3, since "not_reported" doesn't appear in REPORTED_FIELDS at all).
    monkeypatch.setattr(validate, "VALIDATED_FIELDS", ("id", "name", "not_reported"))
    text = render_report(records=[])
    assert f"2 of {len(REPORTED_FIELDS)} reported fields are checked by the validation rules." in text


def test_report_footer_names_each_rejection_reason_with_its_count():
    records = [
        {"id": "A", "name": "A Co", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "B", "name": "Bad Currency", "amount": 100, "currency": "GBP", "region": "NA"},
    ]
    text = render_report(records=records)
    assert "Rejections" in text
    assert "missing id: 1 record" in text
    assert "unknown currency: 1 record" in text


def test_report_footer_pluralises_the_reason_count():
    records = [
        {"name": "No Id 1", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id 2", "amount": 100, "currency": "USD", "region": "NA"},
    ]
    text = render_report(records=records)
    assert "missing id: 2 records" in text
    assert "missing id: 2 record\n" not in text  # not the singular form


def test_report_footer_states_nothing_was_rejected_when_the_feed_is_clean():
    records = [{"id": "A", "name": "A Co", "amount": 100, "currency": "USD", "region": "NA"}]
    text = render_report(records=records)
    assert "Rejections\n----------\nNo records were rejected." in text


def test_report_footer_handles_an_empty_feed():
    text = render_report(records=[])
    assert "Rejections\n----------\nNo records were rejected." in text


def test_report_footer_is_the_last_thing_in_the_report():
    text = render_report()
    lines = text.rstrip("\n").splitlines()
    assert lines[-3] == "Rejections"
    assert lines[-2] == "----------"
    assert lines[-1] == "missing id: 1 record"


def test_report_body_above_the_footer_is_unchanged_by_the_new_footer():
    # Pins that everything through "Validation covers: ..." is still exactly
    # what it was before the footer existed, for the committed feed.
    text = render_report()
    before_footer = text.split("\n\nRejections\n")[0]
    assert before_footer.endswith(
        "Validation covers: id, name, amount, currency, region"
    )
    assert "Rejections" not in before_footer
