"""Tests for the rendered settlement report."""

import pytest

from src.records import load_records
from src.report import _table, render_report
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
    # No row in the shipped feed (data/records.json) has an empty tags column, so this synthetic
    # record is the only thing exercising _cell()'s empty-list-to-"-" branch at all.
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
    # Hardcoded, not derived from validate.VALIDATED_FIELDS / report.REPORTED_FIELDS: id, name,
    # amount, currency, region are checked by check_record() (5); tags is reported but only
    # normalised, not checked (+1) = 6 reported fields total.
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()


@pytest.mark.parametrize("field", ["id", "name"])
def test_report_still_stringifies_a_non_tags_list_value(field):
    # check_record() has no type guard on id/name beyond _missing() -- region/currency/amount each
    # reject a list value outright via their own guards -- so a record with a list-valued id or
    # name is accepted unchanged. _cell()'s tags-only list branch must not fire for these fields:
    # today's formatting for a list value (str([1]) == "[1]") is odd and unintentional, not a
    # designed behaviour, but it must survive unchanged rather than raising TypeError from an
    # unscoped ", ".join(value). Two separate parametrised cases (not one test with two asserts)
    # so a mutation that breaks only one of id/name is attributed to the specific case, not "test
    # 5 in general".
    record = {
        "id": "R-9002",
        "name": "List Value Co",
        "amount": 50,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    record[field] = [1]
    text = render_report(records=[record])
    row_line = text.splitlines()[5]
    assert "[1]" in row_line


def test_report_never_lets_a_tag_forge_an_extra_physical_row():
    # A tag carrying a raw line break reaches _cell() unfiltered by parse_tags() -- a pre-existing
    # gap in src/parse.py that is tracked separately and deliberately not fixed here. _table()
    # must still guarantee exactly one physical output line per logical row it returns: joining
    # its lines with "\n" and splitting again must report the same count that _table() itself
    # returned. Without escaping, a "\n" embedded in a tag turns one logical row into two physical
    # lines, forging what looks like an extra report row.
    rows = [
        {
            "id": "R-9003",
            "name": "Newline Co",
            "region": "NA",
            "amount": 75,
            "currency": "USD",
            "tags": ["high\nforged row, y"],
        }
    ]
    logical_lines = _table(rows)
    physical_lines = "\n".join(logical_lines).split("\n")
    assert len(physical_lines) == len(logical_lines)
