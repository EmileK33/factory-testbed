"""Tests for fee application.

Conversion and counting used to live here too. They were split out into
``test_conversion.py`` and ``test_counts.py`` because each is coupled to a
different committed data file, and holding both in one file forced any two items
touching different data to edit the same test — see this repository's TESTING.md
routing table.
"""

import pytest

from src.normalise import FLAT_FEE, _flat_component, _handling_component, apply_fees, fee_for


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


def test_fee_components_sum_to_the_total():
    record = {"id": "R-9", "amount": 1000, "region": "EU"}
    assert _flat_component(record) == FLAT_FEE
    assert _handling_component(record) == 150
    assert fee_for(record) == _flat_component(record) + _handling_component(record)


def test_fee_for_apac_is_flat_only():
    record = {"id": "R-1", "amount": 1000, "region": "APAC"}
    assert _handling_component(record) == 0
    assert fee_for(record) == FLAT_FEE


def test_fee_for_unknown_region_defaults_handling_to_zero():
    record = {"id": "R-2", "amount": 1000, "region": "ZZ"}
    assert _handling_component(record) == 0
    assert fee_for(record) == FLAT_FEE
