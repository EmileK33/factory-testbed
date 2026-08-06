"""Tests for the feed validation rules."""

import pytest

from src import validate
from src.validate import check_record, evaluate_record

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


# --- evaluate_record(): the same decisions as check_record(), plus why. ---
#
# check_record() and evaluate_record() must never disagree, because the report's
# footer (src/report.py, via src/summarise.py) trusts evaluate_record()'s reason
# exactly when evaluate_record()'s verdict says "rejected". These tests pin both
# halves together rather than the reason alone, so a refactor that lets the two
# drift apart fails here first.


def test_evaluate_record_agrees_with_check_record_on_acceptance():
    normalised, reason = evaluate_record(CLEAN)
    assert reason is None
    assert normalised == check_record(CLEAN)


@pytest.mark.parametrize("field", validate.VALIDATED_FIELDS)
def test_evaluate_record_names_which_field_is_missing(field):
    incomplete = {key: value for key, value in CLEAN.items() if key != field}
    normalised, reason = evaluate_record(incomplete)
    assert normalised is None
    assert check_record(incomplete) is None
    assert reason == f"missing {field}"


def test_evaluate_record_checks_missing_fields_before_region_or_currency():
    # id is first in VALIDATED_FIELDS, so a record missing id AND carrying an
    # unrecognised region reports the missing-id reason, not the region one -
    # pins the check ORDER, not just that each check fires in isolation.
    incomplete = {key: value for key, value in CLEAN.items() if key != "id"}
    incomplete["region"] = "LATAM"
    normalised, reason = evaluate_record(incomplete)
    assert normalised is None
    assert reason == "missing id"


def test_evaluate_record_names_an_unknown_region():
    normalised, reason = evaluate_record({**CLEAN, "region": "LATAM"})
    assert normalised is None
    assert reason == "unknown region"


def test_evaluate_record_names_an_unknown_currency():
    normalised, reason = evaluate_record({**CLEAN, "currency": "GBP"})
    assert normalised is None
    assert reason == "unknown currency"


def test_evaluate_record_names_a_non_whole_amount():
    normalised, reason = evaluate_record({**CLEAN, "amount": True})
    assert normalised is None
    assert reason == "amount is not a whole number"


def test_evaluate_record_names_a_negative_amount():
    normalised, reason = evaluate_record({**CLEAN, "amount": -1})
    assert normalised is None
    assert reason == "amount is negative"


def test_evaluate_record_names_a_record_that_is_not_a_mapping():
    normalised, reason = evaluate_record("not a record")
    assert normalised is None
    assert check_record("not a record") is None
    assert reason == "not a record"
