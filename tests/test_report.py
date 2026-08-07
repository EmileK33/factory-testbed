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


def test_report_shows_each_accepted_records_nonempty_tags():
    text = render_report()
    accepted = [row for row in (check_record(r) for r in load_records()) if row]
    # Guarded to non-empty tag lists deliberately: ", ".join([]) == "", and
    # "" in text is trivially True, so an unguarded assertion here would pass
    # even if tags rendering broke for a record with no tags. The empty case
    # has its own dedicated test below.
    for row in accepted:
        if row["tags"]:
            assert ", ".join(row["tags"]) in text


def test_report_header_includes_a_tags_column():
    header = render_report().splitlines()[3]
    assert "tags" in header.split()


def test_report_states_how_many_reported_fields_are_validated():
    assert "5 of 6 reported fields are checked by the validation rules." in render_report()


def test_report_blanks_a_record_with_no_tags():
    text = render_report(
        records=[
            {
                "id": "Z-1",
                "name": "Zeta Test",
                "amount": 100,
                "currency": "USD",
                "region": "NA",
            }
        ]
    )
    row_line = text.splitlines()[5]
    assert row_line.split()[-1] == "-"
