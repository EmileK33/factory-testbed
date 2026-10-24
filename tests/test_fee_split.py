"""Tests for the split of ``fee_for()`` into its flat and handling components.

The claims here are deliberately narrow: they cover the listed regions and
amounts, not every integer. ``_base_fee`` is a frozen literal copy of the
unsplit expression ``fee_for()`` held before the split.
"""

import pytest

from src import normalise
from src.normalise import FLAT_FEE, HANDLING_BP, fee_for

REGIONS = [*HANDLING_BP, "XX", ""]
AMOUNTS = [0, 1, 2, 9, 10, 99, 100, 333, 667, 9999, 10000, 10001, 19999, 20000, 2**31, 10**18 + 1, -1, -9999]

BASE_PUBLIC_NAMES = {"FLAT_FEE", "HANDLING_BP", "fee_for", "apply_fees", "annotations"}


def _base_fee(record: dict) -> int:
    return FLAT_FEE + record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000


@pytest.mark.parametrize("region", REGIONS)
@pytest.mark.parametrize("amount", AMOUNTS)
def test_fee_for_equals_the_unsplit_expression(region, amount):
    record = {"amount": amount, "region": region}
    assert fee_for(record) == _base_fee(record)


def test_fee_for_returns_the_sum_of_the_two_helpers(monkeypatch):
    monkeypatch.setattr(normalise, "_flat_component", lambda: 1000)
    monkeypatch.setattr(normalise, "_handling_component", lambda record: 20)
    assert fee_for({"amount": 5, "region": "EU"}) == 1020


def test_flat_component_is_the_flat_fee():
    assert normalise._flat_component() == FLAT_FEE


@pytest.mark.parametrize(
    ("region", "amount", "expected"),
    [
        ("EU", 1000, 150),
        ("NA", 1000, 50),
        ("APAC", 1000, 0),
        ("XX", 1000, 0),
        ("EU", 9999, 1499),
        ("NA", 9999, 499),
        ("APAC", 9999, 0),
        ("XX", 9999, 0),
    ],
)
def test_handling_component_is_the_floor_of_the_regional_charge(region, amount, expected):
    assert normalise._handling_component({"amount": amount, "region": region}) == expected


@pytest.mark.parametrize(
    "record",
    [{"amount": 5}, {"region": "EU"}, {}],
    ids=["no-region", "no-amount", "neither"],
)
def test_malformed_records_raise_what_the_unsplit_expression_raised(record):
    with pytest.raises(KeyError) as expected:
        _base_fee(record)
    with pytest.raises(KeyError) as got:
        fee_for(record)
    assert got.value.args == expected.value.args


def test_public_names_are_unchanged():
    public = {name for name in vars(normalise) if not name.startswith("_")}
    assert public == BASE_PUBLIC_NAMES
