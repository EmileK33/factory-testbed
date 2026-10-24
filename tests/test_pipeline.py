"""Tests for fee application.

Conversion and counting used to live here too. They were split out into
``test_conversion.py`` and ``test_counts.py`` because each is coupled to a
different committed data file, and holding both in one file forced any two items
touching different data to edit the same test — see this repository's TESTING.md
routing table.
"""

import pytest

from src import normalise
from src.normalise import apply_fees, fee_for

REGIONS = ("EU", "NA", "APAC", "XX")
NON_NEGATIVE = (0, 1, 99, 100, 1000, 12345, 10001, 999999)
NEGATIVE = (-1, -99, -999, -10001)


def _original_fee_for(record):
    """Frozen copy of the single-expression fee_for() from before the split."""
    return 25 + record["amount"] * {"EU": 1500, "NA": 500, "APAC": 0}.get(record["region"], 0) // 10000


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("amount", NON_NEGATIVE)
def test_fee_for_matches_the_original_expression(amount, region):
    record = {"amount": amount, "region": region}
    assert fee_for(record) == _original_fee_for(record)
    assert type(fee_for(record)) is int


@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("amount", NEGATIVE)
def test_fee_for_keeps_floor_division_for_negative_amounts(amount, region):
    # apply_fees() rejects credits, but fee_for() is public and unguarded.
    record = {"amount": amount, "region": region}
    assert fee_for(record) == _original_fee_for(record)
    assert type(fee_for(record)) is int


def test_flat_component_is_the_flat_fee():
    assert normalise._flat_component({"amount": 1000, "region": "EU"}) == 25


@pytest.mark.parametrize(
    ("region", "expected"), [("EU", 150), ("NA", 50), ("APAC", 0), ("XX", 0)]
)
def test_handling_component_is_the_regional_charge(region, expected):
    assert normalise._handling_component({"amount": 1000, "region": region}) == expected


@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("amount", NEGATIVE + NON_NEGATIVE)
def test_fee_for_is_the_sum_of_its_components(amount, region):
    record = {"amount": amount, "region": region}
    assert fee_for(record) == (
        normalise._flat_component(record) + normalise._handling_component(record)
    )


def test_normalise_public_names_are_unchanged():
    public = sorted(n for n in vars(normalise) if not n.startswith("_"))
    assert public == ["FLAT_FEE", "HANDLING_BP", "annotations", "apply_fees", "fee_for"]
