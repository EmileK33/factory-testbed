"""Counting over the committed feed.

Coupled to ``data/records.json``: a change to the feed moves these expectations
and nothing else in the suite.
"""

from src.records import load_records
from src.summarise import summarise

CLEAN = {
    "id": "R-3001",
    "name": "Test Co",
    "amount": 500,
    "currency": "USD",
    "region": "NA",
    "tags": "na,keep",
}


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 7
    assert counts["rejected_count"] == 1
    assert counts["rejected"] == ["<unlabelled>"]
    # Hand-derived from check_record()'s "tags" list for the 7 accepted records
    # in the committed data/records.json (R-1001..R-1005, R-1007, R-1008; the
    # unlabelled row is the sole rejection). This literal is NOT computed by
    # calling summarise()/check_record() here -- doing so would make the
    # assertion tautological. If data/records.json's accepted rows change,
    # this dict must be re-derived BY HAND from the new accepted set, not
    # patched piecemeal.
    assert counts["by_tag"] == {
        "eu": 3,
        "high": 1,
        "priority": 1,
        "settled": 2,
        "na": 3,
        "apac": 1,
        "bulk": 1,
        "small": 1,
        "crossborder": 1,
        "rail": 1,
        "air": 1,
    }


def test_by_tag_is_empty_when_input_is_empty():
    """The loop body never runs at all -- distinct from the all-rejected case
    below, which runs the loop but takes the rejected branch every time."""
    counts = summarise([])
    assert counts["by_tag"] == {}
    assert counts["rejected_count"] == 0


def test_by_tag_is_empty_when_everything_is_rejected():
    """A non-empty feed where every record fails validation: the loop runs,
    but every iteration takes the ``rejected`` branch, so ``by_tag`` stays
    present and empty rather than absent."""
    all_rejected = [
        {**CLEAN, "id": "R-3002", "currency": "GBP"},
        {**CLEAN, "id": "R-3003", "amount": -1},
    ]
    counts = summarise(all_rejected)
    assert counts["accepted"] == 0
    assert counts["rejected_count"] == 2
    assert counts["by_tag"] == {}


def test_by_tag_counts_accepted_records_only_once_per_tag_even_if_repeated():
    repeated = {**CLEAN, "tags": "eu,eu,settled"}
    counts = summarise([repeated])
    assert counts["by_tag"] == {"eu": 1, "settled": 1}


def test_by_tag_excludes_tags_from_a_rejected_record():
    accepted = {**CLEAN, "id": "R-3004", "tags": "keep"}
    rejected = {**CLEAN, "id": "R-3005", "currency": "GBP", "tags": "drop"}
    counts = summarise([accepted, rejected])
    assert "drop" not in counts["by_tag"]
    assert counts["by_tag"] == {"keep": 1}


def test_by_tag_is_empty_when_no_accepted_record_has_tags():
    no_tags = {**CLEAN, "tags": ""}
    counts = summarise([no_tags])
    assert counts["accepted"] == 1
    assert counts["by_tag"] == {}


def test_by_tag_present_and_rejected_absent_when_everything_is_accepted():
    """Documents, but does not fix, the pre-existing conditional-``rejected``-key
    defect: with nothing rejected, ``rejected`` is absent while ``by_tag`` is
    still present (fully populated), never absent."""
    counts = summarise([CLEAN])
    assert "rejected" not in counts
    assert counts["by_tag"] == {"na": 1, "keep": 1}


def test_by_tag_preserves_tag_case_as_check_record_returns_it():
    upper = {**CLEAN, "id": "R-3006", "tags": "EU"}
    lower = {**CLEAN, "id": "R-3007", "tags": "eu"}
    counts = summarise([upper, lower])
    assert counts["by_tag"] == {"EU": 1, "eu": 1}


def test_summarise_reports_the_rejection_reason_for_the_shipped_feed():
    counts = summarise(load_records())
    assert counts["rejection_reasons"] == [{"reason": "missing id", "count": 1}]


def test_summarise_rejection_reasons_empty_when_nothing_rejected():
    # "rejection_reasons" is always present, unlike the pre-existing, deliberately
    # untouched conditional "rejected" key above -- new callers must not have to
    # special-case a missing key the way that one requires.
    counts = summarise([CLEAN])
    assert counts["rejection_reasons"] == []


def test_summarise_counts_a_multi_reason_record_once():
    record = {**CLEAN, "amount": -5}
    del record["id"]
    counts = summarise([record])
    assert counts["rejection_reasons"] == [{"reason": "missing id", "count": 1}]


def test_summarise_aggregates_two_records_with_the_same_reason():
    r1 = {**CLEAN, "id": "R-3009", "currency": "GBP"}
    r2 = {**CLEAN, "id": "R-3010", "currency": "GBP"}
    counts = summarise([r1, r2])
    assert counts["rejection_reasons"] == [{"reason": "unknown currency", "count": 2}]


def test_summarise_orders_rejection_reasons_by_first_seen_in_the_feed():
    # The issue does not mandate a particular order for the footer's reasons; this pins
    # one deliberately (first-seen-in-the-feed order) so a change to summarise()'s
    # iteration -- e.g. reason_counts.items() silently reversed -- fails a named test
    # instead of going unnoticed. Checked in both feed orders, not just one, so a
    # coincidental match (e.g. if the two reason strings happened to already sort
    # alphabetically the same way) can't hide a real reversal.
    unknown_currency = {**CLEAN, "id": "R-3011", "currency": "GBP"}
    unknown_region = {**CLEAN, "id": "R-3012", "region": "LATAM"}

    counts = summarise([unknown_currency, unknown_region])
    assert counts["rejection_reasons"] == [
        {"reason": "unknown currency", "count": 1},
        {"reason": "unknown region", "count": 1},
    ]

    counts_reversed = summarise([unknown_region, unknown_currency])
    assert counts_reversed["rejection_reasons"] == [
        {"reason": "unknown region", "count": 1},
        {"reason": "unknown currency", "count": 1},
    ]
