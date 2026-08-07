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


def test_flat_component_returns_the_flat_fee():
    assert _flat_component() == 25


def test_handling_component_charges_the_regional_rate():
    assert _handling_component({"amount": 1000, "region": "EU"}) == 150
    assert _handling_component({"amount": 1000, "region": "APAC"}) == 0
    # Unknown region falls back to the HANDLING_BP.get(..., 0) default.
    assert _handling_component({"amount": 1000, "region": "??"}) == 0


def test_handling_component_rounds_toward_negative_infinity():
    # Regression guard: floor division on a negative amount must not be
    # accidentally changed to truncating division by the split.
    assert _handling_component({"amount": -7, "region": "NA"}) == -1


@pytest.mark.parametrize(
    "record",
    [
        {"id": "R-1", "amount": 1000, "region": "EU"},
        {"id": "R-2", "amount": 0, "region": "NA"},
        {"id": "R-3", "amount": 7, "region": "APAC"},
        {"id": "R-4", "amount": -7, "region": "NA"},
        {"id": "R-5", "amount": 500, "region": "??"},
    ],
)
def test_fee_for_equals_flat_plus_handling(record):
    assert fee_for(record) == _flat_component() + _handling_component(record)
