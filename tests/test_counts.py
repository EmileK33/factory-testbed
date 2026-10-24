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


def test_summarise_says_why_the_feed_rejected_what_it_did():
    counts = summarise(load_records())
    assert counts["rejected_count"] == 1
    assert counts["rejected_by_reason"] == {"missing_field": 1}


def _rec(**changes):
    base = {"id": "R", "name": "N", "amount": 1, "currency": "USD", "region": "NA"}
    base.update(changes)
    return {k: v for k, v in base.items() if v is not None}


MIXED = [
    _rec(id="A"),
    5,
    _rec(id=None),
    _rec(id="B", region="LATAM"),
    _rec(id="C", currency="GBP"),
    _rec(id="D", amount="n/a"),
    _rec(id="E", amount=True),
    _rec(id="F", amount=-3),
    _rec(id="G", region="LATAM", amount=-3, currency="GBP"),
    _rec(id="H", region="EU", currency="USD"),
]


def test_summarise_counts_each_record_under_its_first_failing_reason():
    counts = summarise(MIXED)
    assert counts["rejected_by_reason"] == {
        "not_a_record": 1,
        "missing_field": 1,
        "bad_region": 2,
        "bad_currency": 1,
        "non_integer_amount": 2,
        "negative_amount": 1,
    }
    assert counts["accepted"] == 2
    assert counts["rejected_count"] == 8
    assert sum(counts["rejected_by_reason"].values()) == counts["rejected_count"]
    assert counts["rejected_count"] == counts["total"] - counts["accepted"]


def test_summarise_lists_reasons_in_taxonomy_order_not_encounter_order():
    counts = summarise([_rec(id="F", amount=-3), _rec(id="B", region="LATAM"), 5])
    assert list(counts["rejected_by_reason"]) == [
        "not_a_record",
        "bad_region",
        "negative_amount",
    ]


def test_summarise_labels_a_non_dict_record_instead_of_raising():
    counts = summarise([5, None, "x"])
    assert counts["rejected"] == ["<unlabelled>"] * 3
    assert counts["rejected_by_reason"] == {"not_a_record": 3}


def test_summarise_reasons_are_present_and_empty_when_nothing_is_rejected():
    for feed in ([], [_rec(id="A")]):
        counts = summarise(feed)
        assert counts["rejected_count"] == 0
        assert counts["rejected_by_reason"] == {}
        assert "rejected" not in counts
