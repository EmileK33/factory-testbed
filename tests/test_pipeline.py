"""Tests for fee application.

Conversion and counting used to live here too. They were split out into
``test_conversion.py`` and ``test_counts.py`` because each is coupled to a
different committed data file, and holding both in one file forced any two items
touching different data to edit the same test — see this repository's TESTING.md
routing table.
"""

import pytest

from src.normalise import _flat_component, _handling_component, apply_fees, fee_for


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


@pytest.mark.parametrize(
    ("region", "amount", "fee"),
    [
        ("EU", 1000, 175),
        ("NA", 1000, 75),
        ("APAC", 1000, 25),
        ("XX", 1000, 25),
        ("EU", 0, 25),
        ("NA", 999, 25 + 49),
        ("NA", -60, 22),
    ],
)
def test_fee_for_splits_into_flat_and_regional_handling(region, amount, fee):
    record = {"id": "R-9", "amount": amount, "region": region}
    assert fee_for(record) == fee
    assert _flat_component(record) + _handling_component(record) == fee
