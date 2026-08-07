"""Tests for the rendered settlement report."""

import re

from src.normalise import apply_fees
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


def _net_after_fees_lines(text: str) -> list[str]:
    """Return the "Net after fees" section's lines, header through last data row."""
    lines = text.splitlines()
    start = lines.index("Net after fees")
    end = lines.index("", start)
    return lines[start:end]


def _expected_id_width(net_rows: list[dict]) -> int:
    return max([len("id")] + [len(str(row["id"])) for row in net_rows])


def test_net_after_fees_has_a_header_and_underline():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    net_rows = list(apply_fees(accepted))
    id_width = _expected_id_width(net_rows)
    block = _net_after_fees_lines(text)
    assert block[0] == "Net after fees"
    assert block[1] == "--------------"
    assert block[2] == f"{'id'.ljust(id_width)}  {'net'.rjust(8)}"
    assert block[3] == f"{'-' * id_width}  {'-' * 8}"


def test_net_after_fees_columns_align_with_the_header():
    """Regression test for the bug codex caught in review: a header whose `id`
    cell was hardcoded to 2 characters produced a shorter line than the data
    rows (real ids are longer), so the "net" label didn't sit above the net
    values. Every line in the block — header, underline, and each data row —
    must be the same length, or the columns don't line up.
    """
    text = render_report()
    block = _net_after_fees_lines(text)
    header, underline, *data_lines = block[2:]
    assert data_lines, "expected at least one accepted record in the live feed"
    assert len(underline) == len(header)
    for line in data_lines:
        assert len(line) == len(header), line


def test_net_after_fees_per_record_lines_are_unchanged():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    net_rows = list(apply_fees(accepted))
    id_width = _expected_id_width(net_rows)
    block = _net_after_fees_lines(text)
    data_lines = block[4:]
    assert len(data_lines) == len(net_rows)
    for line, row in zip(data_lines, net_rows):
        assert line == f"{str(row['id']).ljust(id_width)}  {row['net']:>8}"


def test_net_after_fees_header_with_no_accepted_records():
    text = render_report(records=[])
    block = _net_after_fees_lines(text)
    assert block[2] == "id       net"
    assert block[3] == "--  --------"
    assert block[4:] == []
