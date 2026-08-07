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
    assert counts["by_tag"]["eu"] == 3
    assert counts["by_tag"]["na"] == 3
    assert counts["by_tag"]["settled"] == 2
    assert counts["by_tag"]["bulk"] == 1
    assert counts["by_tag"]["high,priority"] == 1


def test_summarise_by_tag_counts_a_repeated_tag_once_per_record():
    records = [
        {
            "id": "R-9001",
            "name": "Dup Tag Co",
            "amount": 100,
            "currency": "USD",
            "region": "NA",
            "tags": "eu,eu",
        }
    ]
    counts = summarise(records)
    assert counts["by_tag"] == {"eu": 1}


def test_summarise_by_tag_is_empty_for_no_records():
    assert summarise([])["by_tag"] == {}
