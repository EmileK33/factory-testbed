"""Tests for fee application, counting and conversion."""

import pytest

from src.normalise import (
    HANDLING_BP,
    _flat_component,
    _handling_component,
    apply_fees,
    fee_for,
)
from src.rates import to_usd_cents
from src.records import load_records
from src.summarise import summarise


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


def test_flat_and_handling_components_sum_to_fee_for():
    record = {"id": "R-9", "amount": 999, "region": "EU"}
    assert _flat_component(record) == 25
    assert _handling_component(record) == 999 * HANDLING_BP["EU"] // 10000 == 149
    assert _flat_component(record) + _handling_component(record) == fee_for(record)


def test_fee_for_raises_on_a_record_missing_region():
    # Pins a deliberate ruling, not a live path: check_record() guarantees every
    # record fee_for() is called with today already has a region, so this state
    # is currently unreachable in production. Keep this test anyway — fee_for's
    # signature (record: dict) enforces nothing, so a future second caller could
    # reach it, and this is the guard against silently swallowing that case.
    with pytest.raises(KeyError):
        fee_for({"id": "R-9", "amount": 1000})


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 5
    assert counts["rejected"] == ["<unlabelled>", "R-1007", "R-1008"]


def test_summarise_counts_accepted_records_by_tag():
    # Tags come from check_record()'s normalised, already-split "tags" list
    # (see src/validate.py::check_record and src/parse.py::parse_tags), so
    # this also pins that a comma-quoted tag counts as one tag: R-1001 carries
    # "high,priority" as a single tag, not "high" and "priority" separately.
    counts = summarise(load_records())
    assert counts["by_tag"] == {
        "eu": 2,
        "high,priority": 1,
        "settled": 2,
        "na": 2,
        "apac": 1,
        "bulk": 1,
        "small": 1,
        "crossborder": 1,
    }


def test_summarise_by_tag_counts_a_repeated_tag_once_per_record():
    # by_tag counts *records carrying a tag*, not tag occurrences (the
    # issue's own wording: "the number of accepted records carrying it").
    # None of the real feed's accepted records repeats a tag within its own
    # list, so this is built on a constructed record whose raw tags field
    # produces a repeat through parse_tags: parse_tags('x,x,"x"') returns
    # ['x', 'x', 'x'].
    record = {
        "id": "R-DUP",
        "name": "Dup",
        "amount": 100,
        "currency": "USD",
        "region": "NA",
        "tags": 'x,x,"x"',
    }
    counts = summarise([record])
    assert counts["by_tag"] == {"x": 1}


def test_summarise_by_tag_is_present_and_empty_for_an_empty_feed():
    # by_tag uses the opposite presence convention from "rejected": it is
    # always present, even as {}, rather than omitted when there is nothing
    # to report. An empty feed has nothing rejected either, so this is also
    # the input that would let by_tag silently vanish if it copied rejected's
    # "omit when empty" convention instead of having its own.
    counts = summarise([])
    assert counts == {"total": 0, "accepted": 0, "by_tag": {}}
    assert "rejected" not in counts


def test_to_usd_cents_converts_with_the_committed_rates():
    assert to_usd_cents(450, "USD") == 45000
    assert to_usd_cents(1200, "EUR") == 129600
