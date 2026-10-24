"""Tests for the feed validation rules."""

from src import validate
from src.validate import check_record

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


def test_inspect_record_names_the_first_failing_reason():
    cases = [
        (5, "not_a_record"),
        ({key: v for key, v in CLEAN.items() if key != "id"}, "missing_field"),
        ({**CLEAN, "name": ""}, "missing_field"),
        ({**CLEAN, "region": "LATAM"}, "bad_region"),
        ({**CLEAN, "currency": "GBP"}, "bad_currency"),
        ({**CLEAN, "amount": "n/a"}, "non_integer_amount"),
        ({**CLEAN, "amount": True}, "non_integer_amount"),
        ({**CLEAN, "amount": -1}, "negative_amount"),
    ]
    assert set(code for _record, code in cases) == set(validate.REJECTION_REASONS)
    for record, code in cases:
        assert validate.inspect_record(record) == (None, code), record


def test_inspect_record_counts_a_record_under_its_first_failing_check_only():
    assert validate.inspect_record(
        {**CLEAN, "region": "LATAM", "amount": -1, "currency": "GBP"}
    ) == (None, "bad_region")
    assert validate.inspect_record(
        {"name": "N", "amount": -1, "currency": "GBP", "region": "NA"}
    ) == (None, "missing_field")
    assert validate.inspect_record({**CLEAN, "currency": "GBP", "amount": -1}) == (
        None,
        "bad_currency",
    )


def test_inspect_record_precedence_is_pinned_for_every_adjacent_pair_of_checks():
    no_id = {key: value for key, value in CLEAN.items() if key != "id"}
    pairs = [
        # missing_field before bad_region
        ({**no_id, "region": "LATAM"}, "missing_field"),
        # bad_region before bad_currency
        ({**CLEAN, "region": "LATAM", "currency": "GBP"}, "bad_region"),
        # bad_currency before non_integer_amount
        ({**CLEAN, "currency": "GBP", "amount": "n/a"}, "bad_currency"),
        # non_integer_amount before negative_amount
        ({**CLEAN, "amount": -1.5}, "non_integer_amount"),
        # not_a_record before everything (nothing to be missing from)
        ([], "not_a_record"),
    ]
    for record, code in pairs:
        assert validate.inspect_record(record) == (None, code), record


def test_the_whole_number_label_is_true_for_every_amount_the_check_rejects():
    # The check rejects every non-int, including a float that is numerically whole.
    label = validate.REJECTION_REASONS["non_integer_amount"]
    for amount in (1200.0, 1.5, "n/a", True):
        assert validate.inspect_record({**CLEAN, "amount": amount})[1] == "non_integer_amount"
    assert label == "amount is not a JSON integer"


def test_inspect_record_accepts_a_pair_outside_allowed_pairs():
    # Ruling 6: ALLOWED_PAIRS stays unenforced.
    checked, code = validate.inspect_record({**CLEAN, "region": "EU", "currency": "USD"})
    assert code is None
    assert checked is not None and checked["region"] == "EU"


def test_check_record_agrees_with_inspect_record():
    for record in (CLEAN, 5, {**CLEAN, "amount": -1}, {**CLEAN, "currency": "GBP"}):
        assert check_record(record) == validate.inspect_record(record)[0]


def test_settlement_pairs_are_configured():
    assert hasattr(validate, "ALLOWED_PAIRS")
    assert ("EU", "EUR") in validate.ALLOWED_PAIRS
    assert ("NA", "USD") in validate.ALLOWED_PAIRS
    assert ("APAC", "JPY") in validate.ALLOWED_PAIRS
