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


def test_summarise_counts_accepted_records_by_tag():
    # LITERAL expectations, hand-derived from data/records.json, deliberately
    # not re-derived by calling check_record()/parse_tags() here - comparing
    # the implementation to itself would pass even if both sides shared a
    # mis-parse. R-1001's tags column is quoted ('eu,"high,priority",settled')
    # and src/parse.py has a known mis-parse of quoted commas (tracked
    # separately, see tests/test_report.py), so it splits into FOUR tags
    # ("eu", "high", "priority", "settled") rather than three - by_tag
    # inherits that as-is. Fennel Labs (no id) is rejected and must not
    # contribute its "eu"/"unlabelled" tags to the counts.
    counts = summarise(load_records())
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


def test_summarise_by_tag_is_empty_for_no_records():
    counts = summarise([])
    assert "by_tag" in counts
    assert counts["by_tag"] == {}


def test_summarise_by_tag_excludes_rejected_records():
    accepted = {"id": "R-1", "name": "Keep Co", "amount": 100, "currency": "USD",
                "region": "NA", "tags": "keep"}
    rejected = {"name": "Drop Co", "amount": 50, "currency": "USD",
                "region": "NA", "tags": "drop"}
    counts = summarise([accepted, rejected])
    assert counts["by_tag"] == {"keep": 1}


def test_to_usd_cents_converts_with_the_committed_rates():
    assert to_usd_cents(450, "USD") == 45000
    assert to_usd_cents(1200, "EUR") == 129600
