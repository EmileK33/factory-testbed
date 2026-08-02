"""Tests for the rendered settlement report."""

import re

from src.parse import parse_tags
from src.records import load_records
from src.report import render_report
from src.validate import check_record


def _row_cells(text: str, id_prefix: str) -> list[str]:
    """Split a rendered table row back into its cell values.

    Cells are separated by runs of two or more spaces (the width-padding plus
    the two-space column separator `_table()` joins with); a lone comma or
    single space inside a cell (e.g. a tag) never produces a run that long.
    """
    line = next(line for line in text.splitlines() if line.startswith(id_prefix))
    return re.split(r"\s{2,}", line.strip())


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
    assert _row_cells(text, "R-9001")[-1] == "-"


def test_report_tags_column_round_trips_through_parse_tags():
    # R-1001's tags column in data/records.json is `eu,"high,priority",settled`
    # -- three tags, the middle one containing a comma. src.parse.parse_tags()
    # (fixed by #15) now honours the upstream quoting and recovers exactly
    # those three. The report's tags cell has to preserve that: if it joined
    # tags with a bare "," or ", " the way a naive renderer would, a reader
    # -- or a re-parse -- would see four tags instead of three, silently
    # reintroducing the same defect #15 fixed at the parsing end, just at the
    # output end instead.
    #
    # The expected value below is the known, hardcoded ground truth for
    # R-1001 (not something produced by calling parse_tags() to build its own
    # expectation); parse_tags() is called here only to check the round trip
    # through the *rendered* cell, which is the boundary this test exists to
    # pin.
    expected_tags = ["eu", "high,priority", "settled"]
    text = render_report()
    tags_cell = _row_cells(text, "R-1001")[-1]
    assert parse_tags(tags_cell) == expected_tags


def test_report_does_not_claim_all_fields_are_checked():
    # tags is reported but not one of validate.VALIDATED_FIELDS, so a report
    # that names 6 reported fields can no longer truthfully say "all reported
    # fields are checked by the validation rules." The fix is to not make that
    # claim at all (checked here), not to reword it into a different one.
    text = render_report()
    assert "reported fields are checked by the validation rules" not in text
    assert "Validation covers: id, name, amount, currency, region" in text
