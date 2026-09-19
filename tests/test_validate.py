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


# reject_reason()'s checks run in a fixed sequence: missing id -> missing name -> missing
# amount -> missing currency -> missing region -> unknown region -> unknown currency ->
# amount not a whole number -> negative amount. test_reject_reason_reports_only_the_first_
# of_several_failures above already pins one pairing (missing id wins over negative
# amount, which are five checks apart); it does NOT pin that each check individually
# precedes its immediate neighbour. Reordering just two adjacent checks (e.g. checking
# currency before region, or reversing the missing-fields loop) would still pass every
# test above. Each test below fails a record on exactly one ADJACENT pair of checks and
# asserts the earlier one wins, so any local reordering fails a named test.


def test_reject_reason_prefers_missing_id_over_missing_name():
    record = {key: value for key, value in CLEAN.items() if key not in ("id", "name")}
    assert reject_reason(record) == "missing id"


def test_reject_reason_prefers_missing_name_over_missing_amount():
    record = {key: value for key, value in CLEAN.items() if key not in ("name", "amount")}
    assert reject_reason(record) == "missing name"


def test_reject_reason_prefers_missing_amount_over_missing_currency():
    record = {key: value for key, value in CLEAN.items() if key not in ("amount", "currency")}
    assert reject_reason(record) == "missing amount"


def test_reject_reason_prefers_missing_currency_over_missing_region():
    record = {key: value for key, value in CLEAN.items() if key not in ("currency", "region")}
    assert reject_reason(record) == "missing currency"


def test_reject_reason_prefers_unknown_region_over_unknown_currency():
    record = {**CLEAN, "region": "LATAM", "currency": "GBP"}
    assert reject_reason(record) == "unknown region"


def test_reject_reason_prefers_unknown_currency_over_amount_not_whole_number():
    record = {**CLEAN, "currency": "GBP", "amount": True}
    assert reject_reason(record) == "unknown currency"


def test_reject_reason_prefers_amount_not_whole_number_over_negative_amount():
    # -1.5 fails BOTH checks under either order: it's not an int (fails _is_whole_number)
    # AND it's less than zero. Whole-number-check-first is what "amount is not a whole
    # number" (rather than "negative amount") proves; a mutant checking amount < 0 first
    # would misreport -1.5 as "negative amount" instead.
    record = {**CLEAN, "amount": -1.5}
    assert reject_reason(record) == "amount is not a whole number"
