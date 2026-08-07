"""Tests for the rendered settlement report."""

import re

from src.records import load_records
from src.report import REPORTED_FIELDS, render_report
from src.validate import VALIDATED_FIELDS, check_record

# Columns are joined with a two-space separator (see src/report.py::_table.line);
# a single space inside a cell (e.g. "Aster Holdings") must not be treated as a
# column boundary, so split on runs of 2+ spaces rather than on any whitespace.
_COLUMN_SPLIT = re.compile(r" {2,}")


def _table_rows(text: str) -> list[list[str]]:
    """Return the accepted-records table as a list of per-column cell lists.

    Locates the column header by its first cell ("id") rather than assuming a
    fixed line offset, then reads rows until the table's trailing blank line.
    """
    lines = text.splitlines()
    header_index = next(
        i for i, line in enumerate(lines) if line.split(maxsplit=1)[:1] == ["id"]
    )
    rows = []
    for line in lines[header_index + 2 :]:  # +2 skips the header and its "----" rule
        if not line:
            break
        rows.append(_COLUMN_SPLIT.split(line))
    return rows


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


def test_report_shows_each_accepted_records_tags_in_its_own_row():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    tags_index = REPORTED_FIELDS.index("tags")
    rows_by_id = {row[0]: row for row in _table_rows(text)}
    for record in accepted:
        row = rows_by_id[record["id"]]
        expected = ", ".join(record["tags"]) if record["tags"] else "-"
        assert row[tags_index] == expected, record["id"]


def test_report_renders_a_dash_for_a_record_with_no_tags_column():
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
    }
    text = render_report(records=[record])
    tags_index = REPORTED_FIELDS.index("tags")
    [row] = _table_rows(text)
    assert row[tags_index] == "-"


def test_report_states_how_many_reported_fields_are_validated():
    validated_reported = [f for f in REPORTED_FIELDS if f in VALIDATED_FIELDS]
    expected = (
        f"{len(validated_reported)} of {len(REPORTED_FIELDS)} reported fields "
        "are checked by the validation rules."
    )
    assert expected in render_report()
