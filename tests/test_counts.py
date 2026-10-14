"""Counting over the committed feed.

Coupled to ``data/records.json``: a change to the feed moves these expectations
and nothing else in the suite.
"""

import json
from pathlib import Path

from src.records import load_records
from src.summarise import summarise
from src.validate import REJECTION_REASONS


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 7
    assert counts["rejected"] == ["<unlabelled>"]


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_live_feed_reports_why_its_one_record_was_rejected():
    counts = summarise(load_records())
    assert counts["rejection_reasons"] == {"missing_field": 1}


def test_reason_counts_are_in_check_order_and_sum_to_the_rejected_ids():
    counts = summarise(_fixture("rejections_records.json"))
    assert counts["rejection_reasons"] == {
        "not_a_record": 1,
        "missing_field": 2,
        "unknown_region": 2,
        "unknown_currency": 1,
        "amount_not_whole_number": 2,
        "negative_amount": 1,
    }
    assert list(counts["rejection_reasons"]) == list(REJECTION_REASONS)
    assert sum(counts["rejection_reasons"].values()) == len(counts["rejected"]) == 9
    assert counts["accepted"] == 2


def test_nothing_rejected_leaves_both_keys_absent():
    counts = summarise(_fixture("no_rejections_records.json"))
    assert counts == {"total": 2, "accepted": 2}
