"""Tests for the feed validation rules."""

import pytest

from src import validate
from src.validate import check_record, reject_reason

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


@pytest.mark.parametrize("field", validate.VALIDATED_FIELDS)
def test_reject_reason_names_the_first_missing_field(field):
    incomplete = {key: value for key, value in CLEAN.items() if key != field}
    assert reject_reason(incomplete) == f"missing {field}"


def test_reject_reason_reports_only_the_first_of_several_failures():
    # id and amount are both invalid here (missing id, negative amount); id is checked
    # first (VALIDATED_FIELDS order), so it -- not the negative amount -- is the reason.
    # This pins that a record failing several rules at once is attributed to exactly one
    # reason, matching check_record()'s own early-return order.
    record = {**CLEAN, "amount": -5}
    del record["id"]
    assert reject_reason(record) == "missing id"


def test_reject_reason_names_unknown_region():
    assert reject_reason({**CLEAN, "region": "LATAM"}) == "unknown region"


def test_reject_reason_names_unknown_currency():
    assert reject_reason({**CLEAN, "currency": "GBP"}) == "unknown currency"


def test_reject_reason_names_amount_not_whole_number():
    assert reject_reason({**CLEAN, "amount": True}) == "amount is not a whole number"


def test_reject_reason_names_negative_amount():
    assert reject_reason({**CLEAN, "amount": -1}) == "negative amount"


def test_reject_reason_returns_none_for_a_clean_record():
    assert reject_reason(CLEAN) is None


def test_reject_reason_names_a_non_dict_record():
    assert reject_reason(["not", "a", "dict"]) == "not a record"
