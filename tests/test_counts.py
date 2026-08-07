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


def test_summarise_returns_by_tag_counts_for_the_committed_feed():
    # Pinned as a literal mapping (exact equality, not a subset check) so a
    # future edit to data/records.json that silently drops or adds a tag is
    # caught here rather than passing unnoticed.
    counts = summarise(load_records())
    assert counts["by_tag"] == {
        "eu": 3,
        "high,priority": 1,
        "settled": 2,
        "na": 3,
        "apac": 1,
        "bulk": 1,
        "small": 1,
        "crossborder": 1,
        "rail": 1,
        "air": 1,
    }


def test_summarise_by_tag_excludes_rejected_records():
    # Fennel Labs (the one rejected record, missing "id") carries its own
    # "unlabelled" tag. by_tag must be scoped to accepted records only, so
    # that tag must not appear.
    counts = summarise(load_records())
    assert "unlabelled" not in counts["by_tag"]


def test_summarise_by_tag_counts_a_record_with_a_quoted_comma_tag():
    # R-1001's raw tags column is 'eu,"high,priority",settled'. Only
    # parse_tags()'s CSV-aware split produces "high,priority" as one token;
    # a naive re-split on every comma would produce "high" and "priority"
    # instead. This proves by_tag reads the already-normalised tags list
    # rather than re-splitting the raw column.
    counts = summarise(load_records())
    assert counts["by_tag"]["high,priority"] == 1


def test_summarise_by_tag_counts_a_repeated_tag_within_one_record_once():
    record = {
        "id": "R-9002",
        "name": "Dup Tag Co",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": "eu,eu",
    }
    counts = summarise([record])
    assert counts["by_tag"] == {"eu": 1}


def test_summarise_by_tag_is_an_empty_mapping_when_no_records_are_accepted():
    assert summarise([])["by_tag"] == {}

    all_rejected = [{"name": "No Id Co", "amount": 1, "currency": "USD", "region": "NA"}]
    assert summarise(all_rejected)["by_tag"] == {}


def test_summarise_handles_a_non_dict_record_without_raising():
    counts = summarise(["not-a-dict", None])
    assert counts["total"] == 2
    assert counts["accepted"] == 0
    assert counts["rejected"] == ["<unlabelled>", "<unlabelled>"]
    assert counts["by_tag"] == {}
