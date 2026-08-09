"""Tests for the rendered settlement report."""

from src import validate
from src.records import load_records
from src.report import REPORTED_FIELDS, _cell, _missing, render_report
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


def test_report_binds_tags_to_the_owning_record_row():
    text = render_report(records=[
        {"id": "R-A", "name": "Alpha", "amount": 100, "currency": "USD",
         "region": "NA", "tags": "alpha-only"},
        {"id": "R-B", "name": "Beta", "amount": 200, "currency": "USD",
         "region": "NA", "tags": "beta-only"},
    ])
    row_a = next(line for line in text.splitlines() if line.startswith("R-A"))
    row_b = next(line for line in text.splitlines() if line.startswith("R-B"))
    assert "alpha-only" in row_a and "beta-only" not in row_a
    assert "beta-only" in row_b and "alpha-only" not in row_b


def test_report_header_includes_tags_column():
    text = render_report()
    header = next(line for line in text.splitlines() if line.startswith("id"))
    assert "tags" in header


def test_missing_treats_an_empty_tag_list_as_blank():
    assert _missing([]) is True
    assert _missing(["settled"]) is False


def test_blank_tags_cell_renders_as_a_dash():
    assert _cell({"tags": []}, "tags") == "-"


def test_report_states_reported_and_validated_field_facts():
    text = render_report()
    assert (
        f"Reported fields ({len(REPORTED_FIELDS)}): {', '.join(REPORTED_FIELDS)}"
    ) in text
    assert (
        f"Validated fields ({len(validate.VALIDATED_FIELDS)}): "
        f"{', '.join(validate.VALIDATED_FIELDS)}"
    ) in text
    # Guard the fixture, not a derived claim: today these two field sets genuinely
    # differ (tags is reported but not validated). This pins that the report keeps
    # stating both lists independently rather than folding them back into one
    # derived sentence — it does not assert any relationship between the counts.
    assert set(REPORTED_FIELDS) != set(validate.VALIDATED_FIELDS)
