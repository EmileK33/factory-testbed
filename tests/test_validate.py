"""Tests for the feed validation rules."""

import pytest

from src import validate
from src.validate import REJECTION_REASONS, check_record, rejection_reason

CLEAN = {
    "id": "R-2001",
    "name": "Test Co",
    "amount": 500,
    "currency": "USD",
    "region": "NA",
    "tags": "na,test",
}


def test_check_record_accepts_a_clean_record():
    checked = check_record(CLEAN)
    assert checked is not None
    assert checked["id"] == "R-2001"
    assert checked["amount"] == 500


def test_check_record_requires_every_validated_field():
    for field in validate.VALIDATED_FIELDS:
        incomplete = {key: value for key, value in CLEAN.items() if key != field}
        assert check_record(incomplete) is None, field


def test_check_record_drops_a_record_with_no_id():
    """Deliberately narrow.

    The field-by-field contract is covered by
    ``test_check_record_requires_every_validated_field``; this pins the ``id``
    case on its own because ``id`` is the column upstream exporters actually
    omit, and a regression there must name itself rather than arriving inside
    a loop failure.
    """
    unlabelled = {key: value for key, value in CLEAN.items() if key != "id"}
    assert check_record(unlabelled) is None


def test_check_record_rejects_an_unknown_currency():
    assert check_record({**CLEAN, "currency": "GBP"}) is None


def test_check_record_rejects_a_boolean_amount():
    assert check_record({**CLEAN, "amount": True}) is None
    assert check_record({**CLEAN, "amount": 1}) is not None


def test_check_record_rejects_a_negative_amount():
    assert check_record({**CLEAN, "amount": -1}) is None
    assert check_record({**CLEAN, "amount": 0}) is not None


def test_settlement_pairs_are_configured():
    assert hasattr(validate, "ALLOWED_PAIRS")
    assert ("EU", "EUR") in validate.ALLOWED_PAIRS
    assert ("NA", "USD") in validate.ALLOWED_PAIRS
    assert ("APAC", "JPY") in validate.ALLOWED_PAIRS


# --- rejection reasons (#272) -------------------------------------------------

def _rec(**overrides):
    base = {"id": "X", "name": "n", "amount": 1, "currency": "EUR", "region": "EU"}
    base.update(overrides)
    return base


REASON_SAMPLES = [
    (5, "not_a_record"),
    (_rec(name=""), "missing_field"),
    (_rec(region="MARS"), "unknown_region"),
    (_rec(currency="GBP"), "unknown_currency"),
    (_rec(amount="1"), "amount_not_whole_number"),
    (_rec(amount=True), "amount_not_whole_number"),
    (_rec(amount=-1), "negative_amount"),
    (_rec(), None),
    (_rec(currency="USD"), None),  # outside ALLOWED_PAIRS stays accepted
]


@pytest.mark.parametrize(("record", "code"), REASON_SAMPLES)
def test_rejection_reason_names_the_failing_check(record, code):
    assert rejection_reason(record) == code
    assert (check_record(record) is None) == (code is not None)


def test_every_reason_code_has_a_sample_and_a_label():
    assert {c for _, c in REASON_SAMPLES if c} == set(REJECTION_REASONS)


def test_the_first_failing_check_wins():
    assert rejection_reason(_rec(id="", region="MARS")) == "missing_field"
    assert rejection_reason(_rec(region="MARS", currency="GBP", amount=-1)) == "unknown_region"
    assert rejection_reason(_rec(currency="GBP", amount=-1)) == "unknown_currency"
    assert rejection_reason(_rec(amount=-1.5)) == "amount_not_whole_number"
