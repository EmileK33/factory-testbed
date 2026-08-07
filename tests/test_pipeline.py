"""Tests for fee application.

Conversion and counting used to live here too. They were split out into
``test_conversion.py`` and ``test_counts.py`` because each is coupled to a
different committed data file, and holding both in one file forced any two items
touching different data to edit the same test — see this repository's TESTING.md
routing table.
"""

import pytest

from src.normalise import (
    FLAT_FEE,
    _flat_component,
    _handling_component,
    apply_fees,
    fee_for,
)


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


def test_flat_component_returns_the_flat_fee_regardless_of_region_or_amount():
    assert _flat_component({"amount": 999999, "region": "unknown-region"}) == FLAT_FEE


def test_handling_component_computes_basis_points_of_amount():
    assert _handling_component({"amount": 1000, "region": "EU"}) == 150
    assert _handling_component({"amount": 1000, "region": "unknown"}) == 0


def test_fee_for_still_equals_flat_plus_handling():
    assert fee_for({"amount": 1000, "region": "EU"}) == 175
    assert fee_for({"amount": 1000, "region": "APAC"}) == 25
