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


def test_validate_record_gives_no_reason_for_a_clean_record():
    checked, reason = validate.validate_record(CLEAN)
    assert reason is None
    assert checked == check_record(CLEAN)


def test_validate_record_names_the_reason_for_each_rejection():
    cases = [
        ("not a dict", "record is not an object"),
        ({**CLEAN, "region": "XX"}, "region not recognised"),
        ({**CLEAN, "currency": "GBP"}, "currency not recognised"),
        ({**CLEAN, "amount": "5"}, "amount is not a whole number"),
        ({**CLEAN, "amount": True}, "amount is not a whole number"),
        ({**CLEAN, "amount": -1}, "amount is negative"),
    ]
    for field in validate.VALIDATED_FIELDS:
        cases.append(({k: v for k, v in CLEAN.items() if k != field}, f"{field} missing or empty"))
        cases.append(({**CLEAN, field: ""}, f"{field} missing or empty"))
    for record, expected in cases:
        assert validate.validate_record(record) == (None, expected), record


def test_validate_record_reports_the_first_failing_check_only():
    both = {**CLEAN, "id": None, "currency": "GBP", "amount": -1}
    assert validate.validate_record(both) == (None, "id missing or empty")
    assert validate.validate_record({**CLEAN, "region": "XX", "currency": "GBP"}) == (None, "region not recognised")
    assert validate.validate_record({**CLEAN, "currency": "GBP", "amount": -1}) == (None, "currency not recognised")
    assert validate.validate_record({**CLEAN, "amount": True}) == (None, "amount is not a whole number")


def test_validate_record_reports_the_first_missing_field_in_validated_fields_order():
    fields = validate.VALIDATED_FIELDS
    assert fields == ("id", "name", "amount", "currency", "region")
    for i, first in enumerate(fields):
        for later in fields[i + 1 :]:
            record = {**CLEAN, first: "", later: None}
            assert validate.validate_record(record) == (None, f"{first} missing or empty"), (first, later)
    several = {"id": "", "name": "", "amount": 100, "currency": "USD", "region": "NA"}
    assert validate.validate_record(several) == (None, "id missing or empty")
    assert validate.validate_record({k: v for k, v in CLEAN.items() if k not in fields}) == (
        None,
        "id missing or empty",
    )


def test_a_pair_outside_allowed_pairs_stays_accepted():
    record = {**CLEAN, "region": "EU", "currency": "USD"}
    assert ("EU", "USD") not in validate.ALLOWED_PAIRS
    assert validate.validate_record(record)[1] is None


def test_settlement_pairs_are_configured():
    assert hasattr(validate, "ALLOWED_PAIRS")
    assert ("EU", "EUR") in validate.ALLOWED_PAIRS
    assert ("NA", "USD") in validate.ALLOWED_PAIRS
    assert ("APAC", "JPY") in validate.ALLOWED_PAIRS
