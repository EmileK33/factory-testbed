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
    assert counts["rejected"] == 1
    assert counts["rejected_ids"] == ["<unlabelled>"]
    assert counts["rejection_reasons"] == {"missing id": 1}


def test_summarise_reports_no_rejections_when_nothing_is_rejected():
    counts = summarise([])
    assert counts == {"total": 0, "accepted": 0, "rejected": 0}
    assert "rejected_ids" not in counts
    assert "rejection_reasons" not in counts


def test_summarise_aggregates_multiple_reasons_and_repeats():
    records = [
        {
            "id": "R-9001",
            "name": "One Co",
            "amount": 100,
            "currency": "USD",
            "region": "NA",
        },
        {"name": "No Id A", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id B", "amount": 100, "currency": "USD", "region": "NA"},
        {
            "id": "R-9004",
            "name": "Bad Currency",
            "amount": 100,
            "currency": "GBP",
            "region": "NA",
        },
    ]
    counts = summarise(records)
    assert counts["total"] == 4
    assert counts["accepted"] == 1
    assert counts["rejected"] == 3
    assert counts["rejected_ids"] == ["<unlabelled>", "<unlabelled>", "R-9004"]
    assert counts["rejection_reasons"] == {
        "missing id": 2,
        "unknown currency: GBP": 1,
    }
