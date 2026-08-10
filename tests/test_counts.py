"""Counting over the committed feed.

Coupled to ``data/records.json``: a change to the feed moves these expectations
and nothing else in the suite.
"""

from src.records import load_records
from src.summarise import summarise


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 5
    assert counts["rejected"] == ["<unlabelled>", "R-1007", "R-1008"]
    assert counts["by_tag"] == {
        "eu": 2,
        "high": 1,
        "priority": 1,
        "settled": 2,
        "na": 2,
        "apac": 1,
        "bulk": 1,
        "small": 1,
        "crossborder": 1,
    }


def _accepted(id_, tags):
    return {
        "id": id_,
        "name": id_,
        "amount": 1,
        "currency": "USD",
        "region": "NA",
        "tags": tags,
    }


def test_by_tag_counts_each_distinct_tag_on_a_multi_tag_record():
    counts = summarise([_accepted("R-1", "alpha,beta")])
    assert counts["by_tag"] == {"alpha": 1, "beta": 1}


def test_by_tag_counts_a_tag_shared_across_two_records():
    counts = summarise([_accepted("R-1", "shared"), _accepted("R-2", "shared")])
    assert counts["by_tag"] == {"shared": 2}


def test_by_tag_counts_a_within_record_duplicate_tag_only_once():
    # parse_tags("na,na") returns ["na", "na"] -- unde-duplicated -- so a
    # naive "count every occurrence" implementation would report 2 here.
    # The issue asks for the number of accepted RECORDS carrying a tag, and
    # this is one record, so the correct count is 1.
    counts = summarise([_accepted("R-1", "na,na")])
    assert counts["by_tag"] == {"na": 1}


def test_by_tag_combines_a_within_record_duplicate_with_a_second_record():
    # One record double-counts "na" internally, a second carries it once.
    # Record-counting: 2 (one per record). Occurrence-counting would give 3.
    # A once-per-tag-globally bug would give 1.
    counts = summarise([_accepted("R-1", "na,na"), _accepted("R-2", "na")])
    assert counts["by_tag"] == {"na": 2}


def test_by_tag_excludes_a_rejected_records_tags():
    rejected = {
        "id": "R-1",
        "name": "R-1",
        "amount": "not-a-number",
        "currency": "USD",
        "region": "NA",
        "tags": "ghost",
    }
    counts = summarise([rejected])
    assert counts["accepted"] == 0
    assert counts["by_tag"] == {}


def test_by_tag_ignores_an_accepted_record_with_no_tags():
    counts = summarise([_accepted("R-1", "")])
    assert counts["accepted"] == 1
    assert counts["by_tag"] == {}


def test_by_tag_is_present_and_empty_for_an_all_rejected_feed():
    rejected = {
        "id": "R-1",
        "name": "R-1",
        "amount": "not-a-number",
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    counts = summarise([rejected])
    assert "by_tag" in counts
    assert counts["by_tag"] == {}
