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


def test_summarise_by_tag_counts_accepted_records_carrying_each_tag():
    counts = summarise(load_records())
    assert counts["by_tag"] == {
        "eu": 3,
        "na": 3,
        "apac": 1,
        "settled": 2,
        "high,priority": 1,
        "bulk": 1,
        "small": 1,
        "crossborder": 1,
        "rail": 1,
        "air": 1,
    }


def test_summarise_by_tag_ignores_records_with_no_tags():
    records = [
        {
            "id": "A-1",
            "name": "Alpha",
            "amount": 100,
            "currency": "EUR",
            "region": "EU",
        }
    ]
    counts = summarise(records)
    assert counts["accepted"] == 1
    assert counts["by_tag"] == {}


def test_summarise_by_tag_excludes_rejected_records_even_with_tags():
    records = [
        {
            # Missing "id" -> rejected by check_record(), despite carrying tags.
            "name": "Beta",
            "amount": 50,
            "currency": "USD",
            "region": "NA",
            "tags": "na,urgent",
        }
    ]
    counts = summarise(records)
    assert counts["accepted"] == 0
    assert counts["by_tag"] == {}


def test_summarise_by_tag_counts_a_repeated_tag_once_per_record():
    records = [
        {
            "id": "C-1",
            "name": "Gamma",
            "amount": 25,
            "currency": "JPY",
            "region": "APAC",
            "tags": "dup,dup",
        }
    ]
    counts = summarise(records)
    assert counts["accepted"] == 1
    assert counts["by_tag"] == {"dup": 1}


def test_summarise_by_tag_sums_across_records_sharing_a_tag():
    records = [
        {
            "id": "D-1",
            "name": "Delta",
            "amount": 25,
            "currency": "JPY",
            "region": "APAC",
            "tags": "shared",
        },
        {
            "id": "D-2",
            "name": "Epsilon",
            "amount": 25,
            "currency": "JPY",
            "region": "APAC",
            "tags": "shared,extra",
        },
    ]
    counts = summarise(records)
    assert counts["accepted"] == 2
    assert counts["by_tag"] == {"shared": 2, "extra": 1}
