"""Tests for fee application, counting and conversion."""

import pytest

from src.normalise import FLAT_FEE, HANDLING_BP, apply_fees, fee_for
from src.rates import to_usd_cents
from src.records import load_records
from src.summarise import summarise


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


@pytest.mark.parametrize(
    ("region", "amount", "expected"),
    [
        ("EU", 1000, 25 + 150),
        ("NA", 1000, 25 + 50),
        ("APAC", 1000, 25 + 0),
        ("LATAM", 1000, 25 + 0),  # unknown region falls back to 0bp
    ],
)
def test_fee_for_is_unchanged_across_known_and_unknown_regions(region, amount, expected):
    record = {"id": "R-9", "amount": amount, "region": region}
    assert fee_for(record) == expected
    # Cross-check against the module constants directly, so the test would
    # catch the split dropping or re-deriving either component incorrectly.
    assert expected == FLAT_FEE + amount * HANDLING_BP.get(region, 0) // 10000


def test_fee_for_flat_only_at_zero_amount():
    record = {"id": "R-9", "amount": 0, "region": "EU"}
    assert fee_for(record) == FLAT_FEE


def test_fee_for_reads_amount_before_region():
    # Pins WHICH KeyError fires on a malformed record, which is the observable
    # difference the "identical for every input" invariant actually rests on.
    # Without this, swapping the two accesses inside _handling_component()
    # passes the whole suite while changing behaviour on {} - measured, the
    # mutation survived 36 tests.
    with pytest.raises(KeyError) as amount_first:
        fee_for({})
    assert amount_first.value.args[0] == "amount"

    with pytest.raises(KeyError) as region_next:
        fee_for({"amount": 1000})
    assert region_next.value.args[0] == "region"


def test_summarise_counts_the_feed_it_was_given():
    counts = summarise(load_records())
    assert counts["total"] == len(load_records())
    assert counts["accepted"] == 7
    assert counts["rejected"] == ["<unlabelled>"]


def test_summarise_reports_rejection_reasons_for_the_real_feed():
    counts = summarise(load_records())
    assert counts["rejected_reasons"] == {"missing id": 1}
    # The per-reason total must never drift from the plain accept/reject counts.
    assert sum(counts["rejected_reasons"].values()) == counts["total"] - counts["accepted"]


def test_summarise_rejected_reasons_is_empty_when_nothing_is_rejected():
    # The empty case: a feed where nothing is rejected must still produce a
    # coherent (present, not missing) rejected_reasons value, unlike the
    # existing "rejected" key, which stays absent when there's nothing to list.
    clean_feed = [
        {"id": "R-1", "name": "One", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-2", "name": "Two", "amount": 200, "currency": "EUR", "region": "EU"},
    ]
    counts = summarise(clean_feed)
    assert counts["rejected_reasons"] == {}
    assert "rejected" not in counts


def test_summarise_counts_multiple_rejection_reasons_independently():
    mixed_feed = [
        {"name": "No Id", "amount": 100, "currency": "USD", "region": "NA"},
        {"id": "R-3", "name": "Bad Currency", "amount": 100, "currency": "GBP", "region": "NA"},
        {"id": "R-4", "name": "Bad Currency 2", "amount": 100, "currency": "GBP", "region": "NA"},
        {"id": "R-5", "name": "Negative", "amount": -5, "currency": "USD", "region": "NA"},
    ]
    counts = summarise(mixed_feed)
    assert counts["rejected_reasons"] == {
        "missing id": 1,
        "unknown currency": 2,
        "amount is negative": 1,
    }


def test_to_usd_cents_converts_with_the_committed_rates():
    assert to_usd_cents(450, "USD") == 45000
    assert to_usd_cents(1200, "EUR") == 129600
