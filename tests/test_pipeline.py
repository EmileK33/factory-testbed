"""Tests for fee application.

Conversion and counting used to live here too. They were split out into
``test_conversion.py`` and ``test_counts.py`` because each is coupled to a
different committed data file, and holding both in one file forced any two items
touching different data to edit the same test — see this repository's TESTING.md
routing table.
"""

import pytest

from src.normalise import apply_fees, fee_for


def test_apply_fees_rejects_a_negative_gross_amount():
    with pytest.raises(ValueError):
        apply_fees([{"id": "R-9", "amount": -1, "region": "NA"}])


def test_apply_fees_charges_the_regional_handling_rate():
    [row] = apply_fees([{"id": "R-9", "amount": 1000, "region": "EU"}])
    assert row["net"] == 1000 - (25 + 150)


# The six tests below are regression checks for the flat/handling split
# (issue #240). Each asserts fee_for() equals one concrete, pre-computed
# integer for one concrete input. That establishes only "for this specific
# input, the post-refactor code returns the value the pre-refactor formula
# already returned" — nothing about any input not listed here. The universal
# claim ("identical for every input fee_for accepts") is carried by the diff
# being a token-preserving rearrangement of the original expression, not by
# this finite set of cases; see PLAN.md.


def test_fee_for_direct_call_matches_the_pre_refactor_formula():
    assert fee_for({"amount": 1000, "region": "EU"}) == 175


def test_fee_for_handling_component_floors_after_multiplying_not_before():
    # amount * bp // 10000 (25 + 7*1500//10000 = 26) versus a wrongly
    # reordered (amount // 10000) * bp (25 + 0*1500 = 25). This is the
    # rounding-order divergence risk named in PLAN.md section 4.
    assert fee_for({"amount": 7, "region": "EU"}) == 26


def test_fee_for_zero_bp_region_charges_only_the_flat_fee():
    assert fee_for({"amount": 999, "region": "APAC"}) == 25


def test_fee_for_unknown_region_defaults_the_handling_rate_to_zero():
    # HANDLING_BP.get(region, 0) must stay a .get() with a default, not turn
    # into HANDLING_BP[region], which would raise KeyError for this input.
    assert fee_for({"amount": 50, "region": "ZZ"}) == 25


def test_fee_for_zero_amount_still_charges_the_flat_fee():
    assert fee_for({"amount": 0, "region": "EU"}) == 25


def test_fee_for_negative_amount_matches_the_pre_refactor_formula():
    # fee_for() itself has never guarded against negative amounts -- only
    # apply_fees()'s loop does, before fee_for() is ever called from there.
    # Calling fee_for() directly is therefore still "an input it accepts
    # today" per issue #240, and floor division of a negative product must
    # keep rounding toward negative infinity exactly as the original single
    # expression did.
    assert fee_for({"amount": -7, "region": "EU"}) == 23
