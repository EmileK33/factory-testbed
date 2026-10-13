"""Tests for the rendered settlement report."""

import json
from pathlib import Path

from src import validate
from src.records import load_records
from src.report import _cell, render_report
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


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tags_records.json"


def _fixture_lines() -> list[str]:
    return render_report(json.loads(FIXTURE.read_text(encoding="utf-8"))).splitlines()


def _table_row(prefix: str) -> str:
    # The id also opens a line in the "Net after fees" block; the name column
    # ("Ltd") is what picks the table row.
    (row,) = [line for line in _fixture_lines() if line.startswith(prefix) and "Ltd" in line]
    return row


def test_report_has_a_tags_column_header():
    header = next(line for line in _fixture_lines() if line.startswith("id "))
    assert header.split()[-1] == "tags"


def test_tags_are_joined_with_semicolons_and_a_quoted_comma_stays_one_tag():
    assert _table_row("R-9001").endswith("  eu; high,priority; settled")


def test_empty_and_absent_tags_show_a_dash():
    assert _table_row("R-9002").endswith("  -")
    assert _table_row("R-9003").endswith("  -")


def test_cell_joins_a_list_and_dashes_an_empty_one():
    assert _cell({"tags": ["a", "b"]}, "tags") == "a; b"
    assert _cell({"tags": []}, "tags") == "-"
    assert _cell({"tags": [""]}, "tags") == "-"


def test_footer_states_the_true_validated_count():
    lines = _fixture_lines()
    assert "5 of 6 reported fields are checked by the validation rules." in lines
    assert not any(line.startswith("All ") for line in lines)


def test_tags_are_not_validated():
    assert "tags" not in validate.VALIDATED_FIELDS
    assert "Validation covers: id, name, amount, currency, region" in _fixture_lines()
