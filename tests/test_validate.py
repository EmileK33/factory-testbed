"""Tests for the feed validation rules."""

from src import validate
from src.validate import check_record, rejection_reason

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


def test_check_record_rejects_a_non_numeric_amount():
    # R-1008 in an earlier feed carried amount "n/a"; _is_whole_number()'s
    # isinstance(value, int) check must actually reject a string, not just
    # every non-string the other tests exercise (bool, negative, zero).
    assert check_record({**CLEAN, "amount": "n/a"}) is None


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


def test_rejection_reason_is_none_for_a_clean_record():
    assert rejection_reason(CLEAN) is None


def test_rejection_reason_names_each_missing_field():
    for field in validate.VALIDATED_FIELDS:
        incomplete = {key: value for key, value in CLEAN.items() if key != field}
        assert rejection_reason(incomplete) == f"missing {field}", field


def test_rejection_reason_names_an_unknown_region():
    assert rejection_reason({**CLEAN, "region": "ZZ"}) == "unknown region: ZZ"


def test_rejection_reason_names_an_unknown_currency():
    assert rejection_reason({**CLEAN, "currency": "GBP"}) == "unknown currency: GBP"


def test_rejection_reason_names_a_non_numeric_amount():
    assert rejection_reason({**CLEAN, "amount": "n/a"}) == "amount is not a whole number"


def test_rejection_reason_names_a_boolean_amount():
    assert rejection_reason({**CLEAN, "amount": True}) == "amount is not a whole number"


def test_rejection_reason_names_a_negative_amount():
    assert rejection_reason({**CLEAN, "amount": -1}) == "amount is negative"


def test_rejection_reason_names_a_non_dict_record():
    assert rejection_reason("not a record") == "not a record"
    assert rejection_reason(None) == "not a record"


def test_rejection_reason_and_check_record_agree():
    # The two must never diverge: check_record() is built on top of
    # rejection_reason(), so "accepted by one, rejected by the other" would
    # mean the contract disagrees with itself.
    for record in (
        CLEAN,
        {**CLEAN, "currency": "GBP"},
        {**CLEAN, "amount": -1},
        {key: value for key, value in CLEAN.items() if key != "id"},
    ):
        assert (rejection_reason(record) is None) == (check_record(record) is not None)
