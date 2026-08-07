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


def test_flat_component_is_the_flat_fee_regardless_of_region_or_amount():
    assert _flat_component({"id": "R-1", "amount": 1000, "region": "EU"}) == 25
    assert _flat_component({"id": "R-2", "amount": 0, "region": "LATAM"}) == 25


def test_handling_component_applies_the_regional_basis_points():
    assert _handling_component({"id": "R-1", "amount": 1000, "region": "EU"}) == 150
    assert _handling_component({"id": "R-2", "amount": 1000, "region": "NA"}) == 50
    assert _handling_component({"id": "R-3", "amount": 1000, "region": "APAC"}) == 0
    assert _handling_component({"id": "R-4", "amount": 1000, "region": "LATAM"}) == 0


def test_handling_component_floors_toward_zero_on_a_partial_cent():
    # 333 * 1500 // 10000 == 49.95 floored to 49, not rounded to 50.
    assert _handling_component({"id": "R-5", "amount": 333, "region": "EU"}) == 49


def test_fee_for_equals_the_sum_of_its_two_components():
    records = [
        {"id": "R-1", "amount": 1000, "region": "EU"},
        {"id": "R-2", "amount": 1000, "region": "NA"},
        {"id": "R-3", "amount": 1000, "region": "APAC"},
        {"id": "R-4", "amount": 1000, "region": "LATAM"},
        {"id": "R-5", "amount": 0, "region": "EU"},
    ]
    for record in records:
        assert fee_for(record) == _flat_component(record) + _handling_component(record)

    expected_totals = {"R-1": 175, "R-2": 75, "R-3": 25, "R-4": 25, "R-5": 25}
    for record in records:
        assert fee_for(record) == expected_totals[record["id"]]
