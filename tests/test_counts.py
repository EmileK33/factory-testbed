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


def test_summarise_breaks_down_accepted_records_by_tag():
    counts = summarise(load_records())
    assert counts["by_tag"] == {
        "eu": 3,
        "na": 3,
        "settled": 2,
        "high,priority": 1,
        "apac": 1,
        "bulk": 1,
        "small": 1,
        "crossborder": 1,
        "rail": 1,
        "air": 1,
    }


def test_summarise_by_tag_ignores_rejected_records():
    counts = summarise(
        [
            {
                "id": "A-1",
                "name": "Accepted",
                "amount": 100,
                "currency": "USD",
                "region": "NA",
                "tags": "shared,keepme",
            },
            {
                # No id: rejected by check_record(), so its tags must not count.
                "name": "Rejected",
                "amount": 200,
                "currency": "USD",
                "region": "NA",
                "tags": "shared,dropme",
            },
        ]
    )
    assert counts["accepted"] == 1
    assert counts["by_tag"] == {"shared": 1, "keepme": 1}


def test_summarise_by_tag_does_not_re_split_a_quoted_comma_tag():
    counts = summarise(load_records())
    # "high,priority" is one tag (quoted in the raw column); summarise() must
    # consume check_record()'s already-split list rather than re-splitting the
    # raw string, so it stays a single key, not two.
    assert counts["by_tag"]["high,priority"] == 1
    assert "priority" not in counts["by_tag"]


def test_summarise_by_tag_counts_a_record_at_most_once_per_tag():
    # by_tag counts accepted RECORDS carrying a tag, not tag occurrences: a
    # record whose own tags column repeats a tag must still contribute only 1.
    counts = summarise(
        [
            {
                "id": "B-1",
                "name": "Duplicate Tag",
                "amount": 100,
                "currency": "USD",
                "region": "NA",
                "tags": "eu,eu",
            }
        ]
    )
    assert counts["accepted"] == 1
    assert counts["by_tag"] == {"eu": 1}
