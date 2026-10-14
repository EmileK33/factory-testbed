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
    assert counts["accepted"] == 2
    assert "rejected" not in counts
    assert "rejection_reasons" not in counts

_BASE = {"currency": "EUR", "region": "EU", "name": "n", "amount": 1}


def _rec(rid, **extra):
    return dict(_BASE, id=rid, **extra)


def test_by_tag_counts_the_feed_exactly():
    assert summarise(load_records())["by_tag"] == {
        "air": 1,
        "apac": 1,
        "bulk": 1,
        "crossborder": 1,
        "eu": 3,
        "high,priority": 1,
        "na": 3,
        "rail": 1,
        "settled": 2,
        "small": 1,
    }


def test_by_tag_is_present_and_empty_for_an_empty_feed():
    counts = summarise([])
    assert counts["by_tag"] == {}
    assert "rejected" not in counts


def test_by_tag_ignores_records_without_tags_but_counts_them_accepted():
    counts = summarise([_rec("1"), _rec("2", tags=""), _rec("3", tags=5)])
    assert counts["by_tag"] == {}
    assert counts["accepted"] == 3


def test_by_tag_counts_a_repeated_tag_once_per_record():
    assert summarise([_rec("1", tags="a,a,b"), _rec("2", tags="a")])["by_tag"] == {"a": 2, "b": 1}


def test_by_tag_skips_rejected_records():
    counts = summarise([_rec("1", tags="a"), _rec("2", tags="a", amount=-1)])
    assert counts["by_tag"] == {"a": 1}
    assert counts["rejected"] == ["2"]


def test_by_tag_counts_an_already_split_list_column():
    assert summarise([_rec("1", tags=["eu", "rail"])])["by_tag"] == {"eu": 1, "rail": 1}


def test_by_tag_keeps_a_quoted_comma_tag_whole():
    assert summarise([_rec("1", tags='"a,b",c')])["by_tag"] == {"a,b": 1, "c": 1}
