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


def test_flat_component_is_constant_regardless_of_region_or_amount():
    records = [
        {"id": "R-1", "amount": 0, "region": "EU"},
        {"id": "R-2", "amount": 999_999, "region": "NA"},
        {"id": "R-3", "amount": 42, "region": "APAC"},
        {"id": "R-4", "amount": 42, "region": "UNKNOWN"},
    ]
    for record in records:
        assert _flat_component(record) == 25


def test_handling_component_applies_the_regional_basis_points():
    eu_record = {"id": "R-9", "amount": 1000, "region": "EU"}
    apac_record = {"id": "R-10", "amount": 1000, "region": "APAC"}

    assert _handling_component(eu_record) == 1000 * 1500 // 10000
    assert _handling_component(apac_record) == 1000 * 0 // 10000

    for record in (eu_record, apac_record):
        assert _flat_component(record) + _handling_component(record) == fee_for(record)
