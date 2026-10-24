"""Counting over the committed feed.

Coupled to ``data/records.json``: a change to the feed moves these expectations
and nothing else in the suite.
"""

from src.records import load_records
from src.summarise import summarise


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 5
    assert counts["rejected"] == ["<unlabelled>", "R-1007", "R-1008"]


def _record(record_id, **extra):
    base = {"id": record_id, "name": "N " + record_id, "amount": 100, "currency": "USD", "region": "NA"}
    return {**base, **extra}


def test_by_tag_counts_accepted_records_of_the_feed():
    assert summarise(load_records())["by_tag"] == {
        "apac": 1,
        "bulk": 1,
        "crossborder": 1,
        "eu": 2,
        "high,priority": 1,
        "na": 2,
        "settled": 2,
        "small": 1,
    }


def test_by_tag_counts_a_repeated_tag_once_per_record_and_is_case_sensitive():
    counts = summarise([_record("R-1", tags="a,a, b ,A"), _record("R-2", tags="a")])
    assert counts["by_tag"] == {"A": 1, "a": 2, "b": 1}


def test_by_tag_ignores_rejected_records():
    counts = summarise([_record("R-1", tags="a"), _record("R-2", amount=-5, tags="a,zzz")])
    assert counts["by_tag"] == {"a": 1}


def test_by_tag_is_present_and_empty_when_nothing_is_counted():
    assert summarise([])["by_tag"] == {}
    assert summarise([_record("R-1", amount=-1, tags="a")])["by_tag"] == {}
    assert summarise([_record("R-1")])["by_tag"] == {}


def test_by_tag_keys_are_sorted_and_old_keys_keep_their_shape():
    counts = summarise([_record("R-1", tags="z,m,a")])
    assert list(counts["by_tag"]) == ["a", "m", "z"]
    assert counts == {"total": 1, "accepted": 1, "by_tag": {"a": 1, "m": 1, "z": 1}}


def test_by_tag_agrees_with_the_report_tags_column():
    from src.report import render_report

    records = [_record("R-1", tags='eu,"high,priority",eu'), _record("R-2", tags="eu"), _record("R-3")]
    lines = render_report(records).split("\n")
    header = lines[lines.index("Settlement report") + 3]
    offset = header.index("tags")
    rows = lines[lines.index("Settlement report") + 5 : lines.index("", lines.index("Settlement report") + 3)]
    shown: dict[str, int] = {}
    for row in rows:
        cell = row[offset:].rstrip()
        if cell != "-":
            for tag in set(cell.split("; ")):
                shown[tag] = shown.get(tag, 0) + 1
    assert len(rows) == 3
    assert shown == summarise(records)["by_tag"] == {"eu": 2, "high,priority": 1}
