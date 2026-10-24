"""Tests for the rendered settlement report."""

import csv
import json
import re
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


FEED = Path(__file__).resolve().parent.parent / "data" / "records.json"


def _table_cells(text):
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("id "))
    rows = []
    for line in lines[start + 2 :]:
        if not line.strip():
            break
        rows.append(re.split(r"\s{2,}", line.rstrip()))
    return re.split(r"\s{2,}", lines[start].rstrip()), rows


def _record(**changes):
    base = {
        "id": "R-9",
        "name": "N",
        "amount": 1,
        "currency": "USD",
        "region": "NA",
        "tags": "na",
    }
    base.update(changes)
    return base


def test_report_puts_tags_last_in_the_header():
    header, _rows = _table_cells(render_report())
    assert header[-1] == "tags"


def test_report_tags_cells_match_the_raw_feed():
    # Ground truth from the raw feed through csv, not through src.parse.
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    raw_by_id = {r["id"]: r["tags"] for r in feed if r.get("id")}
    _header, rows = _table_cells(render_report())
    assert rows
    for row in rows:
        expected = "; ".join(next(csv.reader([raw_by_id[row[0]]], skipinitialspace=True)))
        assert row[-1] == expected
    assert dict((row[0], row[-1]) for row in rows)["R-1001"] == "eu; high,priority; settled"


def test_report_shows_a_dash_for_a_record_without_tags():
    _header, rows = _table_cells(render_report([_record(tags="")]))
    assert rows == [["R-9", "N", "NA", "1", "USD", "-"]]


def test_report_shows_a_tag_containing_a_separator_verbatim():
    # Known limit: the "; " join is not escaped, so this reads like two tags.
    _header, rows = _table_cells(render_report([_record(tags='"a; b",c')]))
    assert rows[0][-1] == "a; b; c"


def test_report_footer_states_the_true_checked_count():
    text = render_report()
    header, _rows = _table_cells(text)
    assert "5 of 6 reported fields are checked by the validation rules." in text
    assert len(header) == 6
    assert "All " not in "".join(line for line in text.split("\n") if "reported fields" in line)


def test_report_footer_count_is_derived_from_the_field_constants(monkeypatch):
    from src import report, validate

    monkeypatch.setattr(report, "REPORTED_FIELDS", ("id", "name", "tags"))
    monkeypatch.setattr(validate, "VALIDATED_FIELDS", ("id", "name", "amount"))
    text = report.render_report([_record(tags="a")])
    assert "2 of 3 reported fields are checked by the validation rules." in text
    monkeypatch.setattr(validate, "VALIDATED_FIELDS", ("id",))
    assert "1 of 3 reported fields" in report.render_report([_record(tags="a")])


def _footer(text):
    lines = text.split("\n")
    start = max(i for i, line in enumerate(lines) if line.startswith("Validation covers:"))
    assert lines[start + 1] == ""
    return lines[start + 2 :]


def test_report_ends_with_the_rejection_footer_for_the_real_feed():
    assert _footer(render_report()) == ["Rejections by reason:", "  missing field: 1", ""]


def test_report_footer_for_a_feed_that_rejects_nothing():
    for feed in ([], [_record()]):
        assert _footer(render_report(feed)) == ["No records were rejected.", ""]
        assert "Rejections by reason" not in render_report(feed)


def test_report_footer_counts_sum_to_records_rejected():
    mixed = [
        _record(id="A"),
        5,
        {k: v for k, v in _record().items() if k != "id"},
        _record(id="B", region="LATAM"),
        _record(id="C", currency="GBP"),
        _record(id="D", amount="n/a"),
        _record(id="E", amount=True),
        _record(id="F", amount=-3),
        _record(id="G", region="LATAM", amount=-3, currency="GBP"),
        _record(id="H", region="EU", currency="USD"),
    ]
    text = render_report(mixed)
    footer = _footer(text)
    assert footer[0] == "Rejections by reason:"
    counts = [int(line.rsplit(": ", 1)[1]) for line in footer[1:-1]]
    assert footer[-1] == ""
    assert f"Records rejected: {sum(counts)}" in text
    assert footer[1:-1] == [
        "  record is not an object: 1",
        "  missing field: 1",
        "  unrecognised region: 2",
        "  unrecognised currency: 1",
        "  amount is not a JSON integer: 2",
        "  amount is negative: 1",
    ]


def test_report_renders_a_non_dict_entry():
    text = render_report([5, _record()])
    assert "Records rejected: 1" in text
    assert "  record is not an object: 1" in text


def test_footer_is_presented_from_the_summary(monkeypatch):
    from src import report, validate

    real = report.summarise

    def fake(records):
        out = real(records)
        out["rejected_by_reason"] = {"bad_region": 41}
        return out

    monkeypatch.setattr(report, "summarise", fake)
    assert "  unrecognised region: 41" in report.render_report([_record(amount=-1)])
    monkeypatch.setattr(
        validate, "REJECTION_REASONS", {**validate.REJECTION_REASONS, "bad_region": "X"}
    )
    assert "  X: 41" in report.render_report([_record(amount=-1)])


def test_report_names_the_unlabelled_record():
    assert "Unlabelled records: Fennel Labs" in render_report()
