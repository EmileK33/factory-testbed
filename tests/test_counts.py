"""Counting over the committed feed.

Coupled to ``data/records.json``: a change to the feed moves these expectations
and nothing else in the suite.
"""

from src.records import load_records
from src.summarise import summarise


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 7
    assert counts["rejected"] == ["<unlabelled>"]
    assert counts["rejected_count"] == 1
    assert counts["rejected_reasons"] == {"missing id": 1}


def test_summarise_groups_rejections_by_reason_and_counts_each():
    records = [
        {"id": "A", "name": "A Co", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id 1", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "B", "name": "Bad Currency", "amount": 100, "currency": "GBP", "region": "NA"},
        {"name": "No Id 2", "amount": 100, "currency": "USD", "region": "NA"},
    ]
    counts = summarise(records)
    assert counts["accepted"] == 1
    assert counts["rejected_count"] == 3
    # first-seen order: "missing id" appears (record 2) before "unknown
    # currency" (record 3), regardless of each reason's eventual total count.
    assert list(counts["rejected_reasons"]) == ["missing id", "unknown currency"]
    assert counts["rejected_reasons"] == {"missing id": 2, "unknown currency": 1}
    assert counts["rejected"] == ["<unlabelled>", "B", "<unlabelled>"]


def test_summarise_rejected_reasons_is_empty_when_nothing_is_rejected():
    records = [{"id": "A", "name": "A Co", "amount": 100, "currency": "USD", "region": "NA"}]
    counts = summarise(records)
    assert counts["accepted"] == 1
    assert counts["rejected_count"] == 0
    assert counts["rejected_reasons"] == {}
    assert "rejected" not in counts


def test_summarise_handles_an_empty_feed():
    counts = summarise([])
    assert counts == {
        "total": 0,
        "accepted": 0,
        "rejected_count": 0,
        "rejected_reasons": {},
    }


def test_summarise_does_not_crash_on_a_non_dict_record():
    counts = summarise([["not", "a", "dict"]])
    assert counts["rejected_count"] == 1
    assert counts["rejected_reasons"] == {"not a record": 1}
    assert counts["rejected"] == ["<unlabelled>"]
