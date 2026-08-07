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
    assert counts["rejected_by_reason"] == {"missing id": 1}


def test_summarise_reports_no_rejection_reasons_when_nothing_is_rejected():
    clean = {
        "id": "R-9001",
        "name": "No Tags Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    counts = summarise([clean])
    assert counts["accepted"] == 1
    assert "rejected" not in counts
    assert counts["rejected_by_reason"] == {}
