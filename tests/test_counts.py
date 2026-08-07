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
