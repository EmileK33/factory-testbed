"""Tests for the rendered settlement report."""

import json
from pathlib import Path

from src import report, validate
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


def test_footer_count_is_derived_from_the_two_field_lists(monkeypatch):
    # Dropping a reported field must drop it from both numbers; a count taken
    # from len(VALIDATED_FIELDS) alone would still say 5.
    monkeypatch.setattr(
        report, "REPORTED_FIELDS", ("id", "name", "region", "amount", "tags")
    )
    lines = _fixture_lines()
    assert "4 of 5 reported fields are checked by the validation rules." in lines


# --- rejection footer (#272) --------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _report_lines(name: str) -> list[str]:
    records = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return render_report(records).splitlines()


def test_footer_on_the_live_feed_closes_the_report():
    assert render_report().splitlines()[-4:] == [
        "",
        "Rejections by reason",
        "--------------------",
        "missing a required field: 1",
    ]


def test_footer_lists_each_reason_once_with_its_count():
    lines = _report_lines("rejections_records.json")
    assert lines[-8:] == [
        "Rejections by reason",
        "--------------------",
        "not a record: 1",
        "missing a required field: 2",
        "region not recognised: 2",
        "currency not recognised: 1",
        "amount is not an integer: 2",
        "amount is negative: 1",
    ]
    assert lines[-9] == ""


def test_footer_counts_sum_to_records_rejected():
    lines = _report_lines("rejections_records.json")
    rejected = int(next(x for x in lines if x.startswith("Records rejected: ")).split(": ")[1])
    start = lines.index("Rejections by reason") + 2
    assert rejected == 9
    assert sum(int(x.rsplit(": ", 1)[1]) for x in lines[start:]) == rejected


def test_footer_says_so_when_nothing_was_rejected():
    lines = _report_lines("no_rejections_records.json")
    assert lines[-3:] == ["Rejections by reason", "--------------------", "No records were rejected."]
    assert "Records rejected: 0" in lines


def test_a_pair_outside_allowed_pairs_is_accepted_not_a_footer_reason():
    lines = _report_lines("rejections_records.json")
    assert any(x.startswith("M2 ") and "EU" in x and "USD" in x for x in lines)


def test_footer_presents_the_summary_and_derives_nothing(monkeypatch):
    # Values chosen to differ from what the 2-record fixture would give itself.
    fake = {"total": 9, "accepted": 4, "rejected": ["a", "b", "c", "d", "e"],
            "rejection_reasons": {"negative_amount": 2}}
    monkeypatch.setattr(report, "summarise", lambda raw: fake)
    lines = render_report(json.loads((FIXTURES / "no_rejections_records.json").read_text(encoding="utf-8"))).splitlines()
    assert lines[-1] == "amount is negative: 2"
    assert "Records read: 9" in lines
    assert "Records accepted: 4" in lines
    assert "Records rejected: 5" in lines
