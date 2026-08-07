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
    assert counts["rejection_reasons"] == {"missing id": 1}


def test_summarise_rejected_count_is_present_even_when_nothing_was_rejected():
    """``rejected_count`` is unconditional, unlike ``rejected``/``rejection_reasons``.

    The report renderer reads ``rejected_count`` directly for every feed,
    including one with no rejections at all, so it must never be missing.
    """
    counts = summarise(
        [
            {
                "id": "R-1",
                "name": "Clean Co",
                "amount": 100,
                "currency": "USD",
                "region": "NA",
            }
        ]
    )
    assert counts["accepted"] == 1
    assert counts["rejected_count"] == 0
    assert "rejected" not in counts
    assert "rejection_reasons" not in counts


def test_summarise_tallies_multiple_rejection_reasons():
    records = [
        {"name": "No Id A", "amount": 100, "currency": "USD", "region": "NA"},
        {"name": "No Id B", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-2", "name": "Bad Currency", "amount": 100, "currency": "GBP", "region": "NA"},
    ]
    counts = summarise(records)
    assert counts["rejected_count"] == 3
    assert counts["rejection_reasons"] == {"missing id": 2, "unknown currency": 1}
