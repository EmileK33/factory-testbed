"""Tests for the rendered settlement report."""

import json
from pathlib import Path

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


def test_report_still_carries_the_validation_coverage_line_just_above_the_footer():
    from tools.write_golden import summarise_artifact

    lines = render_report().splitlines()
    coverage = "Validation covers: id, name, amount, currency, region"
    assert lines.index(coverage) == len(lines) - 4
    assert lines[-3] == ""
    assert summarise_artifact() == coverage


MIXED = Path(__file__).parent / "fixtures" / "rejections" / "mixed.json"


def _mixed():
    return json.loads(MIXED.read_text(encoding="utf-8"))


def test_report_ends_with_the_rejection_footer_for_the_shipped_feed():
    assert render_report().endswith("\n\nRejected records: 1\n  id missing or empty: 1\n")


def test_report_footer_lists_each_reason_with_its_own_count():
    # Distinct counts per reason: a renderer printing one number for every line fails here.
    feed = _mixed() + [_record("R-8", amount=-1), _record("R-9", amount=-2), _record("R-10", amount=-3)]
    text = render_report(feed)
    assert text.endswith(
        "\n\nRejected records: 8\n"
        "  amount is negative: 4\n"
        "  amount is not a whole number: 1\n"
        "  currency not recognised: 1\n"
        "  id missing or empty: 1\n"
        "  region not recognised: 1\n"
    )


def test_report_footer_for_the_mixed_feed_counts_a_record_under_its_first_reason_only():
    text = render_report(_mixed())
    assert text.endswith(
        "\n\nRejected records: 5\n"
        "  amount is negative: 1\n"
        "  amount is not a whole number: 1\n"
        "  currency not recognised: 1\n"
        "  id missing or empty: 1\n"
        "  region not recognised: 1\n"
    )
    assert "Records rejected: 5\n" in text


def test_report_footer_when_nothing_is_rejected_says_none():
    text = render_report([_record("R-1"), _record("R-2")])
    assert text.endswith("\n\nRejected records: none\n")
    assert "Records rejected: 0\n" in text
    assert "  id missing" not in text


def test_report_presents_the_summary_it_is_given(monkeypatch):
    from src import report

    fake = {"total": 42, "accepted": 39, "rejected": ["a", "b", "c"], "rejected_by_reason": {"zzz fake reason": 3}}
    monkeypatch.setattr(report, "summarise", lambda records: fake)
    text = render_report([_record("R-1")])
    assert "Records read: 42\n" in text
    assert "Records accepted: 39\n" in text
    assert "Records rejected: 3\n" in text
    assert text.endswith("\n\nRejected records: 3\n  zzz fake reason: 3\n")


def test_report_above_the_footer_is_unchanged_for_a_clean_feed():
    text = render_report([_record("R-1")])
    assert "Records rejected: 0\n\nTotal (USD):" in text


def test_report_names_the_unlabelled_record():
    assert "Unlabelled records: Fennel Labs" in render_report()
