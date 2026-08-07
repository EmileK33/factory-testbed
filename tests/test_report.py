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


def test_report_includes_the_tags_column_header():
    header = render_report().splitlines()[3]
    assert "tags" in header.split()


def test_report_puts_each_accepted_records_tags_on_its_row():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    for row in accepted:
        row_line = next(line for line in text.splitlines() if line.startswith(row["id"]))
        assert row_line.rstrip().endswith(", ".join(row["tags"]))


def test_report_shows_a_dash_for_a_record_with_no_tags():
    record = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    text = render_report(records=[record])
    row_line = next(line for line in text.splitlines() if line.startswith("R-9001"))
    assert row_line.rstrip().endswith("-")


def test_report_reports_accurate_validation_coverage():
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()


def test_report_footer_lists_rejection_reasons_with_counts():
    text = render_report()
    lines = text.splitlines()
    assert "Rejected records" in lines
    header_index = lines.index("Rejected records")
    assert lines[header_index + 1] == "-" * len("Rejected records")
    assert "missing id: 1" in lines[header_index + 2 :]


def test_report_footer_handles_the_empty_case():
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
    header_index = lines.index("Rejected records")
    assert lines[header_index + 1] == "-" * len("Rejected records")
    assert lines[header_index + 2] == "No records were rejected."
    # And no stray reason line sneaks in after it.
    assert lines[header_index + 2 :] == ["No records were rejected."]


def test_report_footer_reason_counts_sum_to_records_rejected():
    """Regression guard for the drift this issue is about: the footer's per-reason

    counts must always add up to the same total the report already prints as
    ``Records rejected: N`` — both are sourced from summarise(), never recomputed
    independently in the renderer.
    """
    text = render_report()
    lines = text.splitlines()
    rejected_line = next(line for line in lines if line.startswith("Records rejected: "))
    expected_total = int(rejected_line.removeprefix("Records rejected: "))

    header_index = lines.index("Rejected records")
    reason_lines = lines[header_index + 2 :]
    total = sum(int(line.rsplit(": ", 1)[1]) for line in reason_lines if ": " in line)
    assert total == expected_total


def test_report_footer_sorts_multiple_reasons_alphabetically():
    """The committed feed only ever produces one rejection reason, so on its own it

    can't exercise the footer's sort. Feed order here is deliberately the reverse
    of alphabetical order, so this fails if the footer ever silently reverted to
    feed/insertion order instead of a stable, presentation-only sort.
    """
    bad_currency = {
        "id": "R-9002",
        "name": "Bad Currency Co",
        "amount": 30,
        "currency": "GBP",
        "region": "NA",
        "tags": "",
    }
    missing_id = {
        "name": "No Id Co",
        "amount": 10,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    text = render_report(records=[bad_currency, missing_id])
    lines = text.splitlines()
    header_index = lines.index("Rejected records")
    reason_lines = lines[header_index + 2 :]
    assert reason_lines == ["missing id: 1", "unrecognised currency: 1"]
