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
    # LITERAL expectations, deliberately not derived from check_record().
    # The earlier form built the expected string by calling check_record() again,
    # so both sides of the assertion came from the same parse_tags() call: it
    # could catch a rendering bug in report.py but was structurally incapable of
    # catching a MIS-PARSE, because the mis-parse appeared identically on both
    # sides. A test comparing the implementation to itself passes by construction.
    text = render_report()
    for expected in ("na, settled", "apac, bulk", "na, small", "eu, crossborder"):
        assert expected in text, "expected tag rendering %r missing" % expected


def test_report_renders_a_quoted_tag_as_the_feed_declares_it():
    # R-1001's tags column is 'eu,"high,priority",settled'. parse.py's own
    # docstring says a tag containing a comma is wrapped in double quotes, so
    # this record carries THREE tags and the middle one is "high,priority".
    # src/parse.py now honours that quoting (issue #87), so this asserts
    # normally instead of being pinned as a known-wrong xfail.
    text = render_report()
    assert "eu, high,priority, settled" in text


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


# --- The rejection footer: closes the report, sourced only from summarise(). ---


def test_report_footer_lists_the_rejection_reason_and_count():
    text = render_report()
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    assert lines[header_index + 1] == "-" * len("Rejected records")
    assert lines[header_index + 2] == "missing id: 1"
    # Nothing trails the footer.
    assert len(lines) == header_index + 3


def test_report_footer_states_no_rejections_when_the_feed_is_clean():
    # The empty case: a feed in which nothing is rejected must still produce a
    # coherent footer - an explicit line, not a silently-omitted section (the
    # defect the existing "Unlabelled records" guard has: it just disappears
    # when there's nothing to report).
    clean_records = [
        {"id": "R-1", "name": "One", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-2", "name": "Two", "amount": 200, "currency": "EUR", "region": "EU"},
    ]
    text = render_report(records=clean_records)
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    assert lines[header_index + 1] == "-" * len("Rejected records")
    assert lines[header_index + 2] == "No records were rejected."
    assert len(lines) == header_index + 3


def test_report_footer_lists_multiple_reasons_each_on_its_own_line():
    mixed_records = [
        {"id": "R-1", "name": "One", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-3", "name": "Bad Currency", "amount": 100, "currency": "GBP", "region": "NA"},
    ]
    text = render_report(records=mixed_records)
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    assert lines[header_index + 2] == "missing id: 1"
    assert lines[header_index + 3] == "unknown currency: 1"
    assert len(lines) == header_index + 4


def test_report_footer_reason_total_matches_the_records_rejected_line():
    text = render_report()
    assert "Records rejected: 1" in text
    assert "missing id: 1" in text
