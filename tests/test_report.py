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


def _record(record_id, **extra):
    base = {"id": record_id, "name": "N " + record_id, "amount": 100, "currency": "USD", "region": "NA"}
    return {**base, **extra}


def _table(text):
    lines = text.split("\n")
    start = lines.index("Settlement report") + 3
    end = lines.index("", start)
    return lines[start:end]


def test_report_shows_each_records_tags_as_the_last_column():
    text = render_report(
        [
            _record("R-9001", tags='eu,"high,priority",settled'),
            _record("R-9002", tags=""),
            _record("R-9003"),
            _record("R-9004", tags=["a", None, "b c"]),
        ]
    )
    header, divider, *rows = _table(text)
    assert header.endswith("  tags")
    assert divider.endswith("  " + "-" * len("eu; high,priority; settled"))
    cells = {row.split()[0]: row for row in rows}
    assert cells["R-9001"].endswith("  eu; high,priority; settled")
    assert cells["R-9002"].endswith("  -")
    assert cells["R-9003"].endswith("  -")
    assert cells["R-9004"].endswith("  a; b c")
    assert all(row == row.rstrip() for row in rows)


def test_report_footer_states_the_true_count_of_validated_fields():
    from src import report, validate

    lines = render_report([_record("R-9001", tags="a")]).split("\n")
    assert "tags" not in validate.VALIDATED_FIELDS
    assert "5 of 6 reported fields are checked by the validation rules." in lines
    assert not any(line.startswith("All ") and "reported fields" in line for line in lines)
    checked = [f for f in report.REPORTED_FIELDS if f in validate.VALIDATED_FIELDS]
    assert len(checked) == 5


def test_report_still_ends_with_the_validation_coverage_line():
    from tools.write_golden import summarise_artifact

    last = render_report().splitlines()[-1]
    assert last == "Validation covers: id, name, amount, currency, region"
    assert summarise_artifact() == last


def test_report_names_the_unlabelled_record():
    assert "Unlabelled records: Fennel Labs" in render_report()
