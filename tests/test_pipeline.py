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
    assert counts["accepted"] == 5
    assert counts["rejected"] == ["<unlabelled>", "R-1007", "R-1008"]


def test_to_usd_cents_converts_with_the_committed_rates():
    assert to_usd_cents(450, "USD") == 45000
    assert to_usd_cents(1200, "EUR") == 129600
