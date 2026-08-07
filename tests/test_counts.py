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


def test_summarise_tallies_multiple_records_under_the_same_reason():
    """The committed feed only ever produces one rejection, so on its own it can't

    exercise the accumulation (`+= 1` per repeat reason) or multi-reason branches
    of ``rejected_by_reason``. This pins both against a synthetic feed.
    """
    missing_id_a = {
        "name": "No Id A",
        "amount": 10,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    missing_id_b = {
        "name": "No Id B",
        "amount": 20,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    bad_currency = {
        "id": "R-9002",
        "name": "Bad Currency Co",
        "amount": 30,
        "currency": "GBP",
        "region": "NA",
        "tags": "",
    }
    counts = summarise([missing_id_a, missing_id_b, bad_currency])
    assert counts["accepted"] == 0
    assert counts["rejected_by_reason"] == {"missing id": 2, "unrecognised currency": 1}
