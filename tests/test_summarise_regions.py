"""Tests for the per-region totals helper."""

from src.summarise import region_totals

EU = {"id": "R-1", "name": "Alpha", "amount": 100, "currency": "EUR", "region": "EU"}
NA = {"id": "R-2", "name": "Beta", "amount": 250, "currency": "USD", "region": "NA"}
APAC = {"id": "R-3", "name": "Gamma", "amount": 700, "currency": "JPY", "region": "APAC"}


def test_region_totals_groups_accepted_records_by_region():
    totals = region_totals([EU, NA, APAC])
    assert totals == {
        "EU": {"accepted": 1, "gross": 100},
        "NA": {"accepted": 1, "gross": 250},
        "APAC": {"accepted": 1, "gross": 700},
    }


def test_region_totals_sums_repeated_regions():
    records = [EU, {**EU, "id": "R-4", "amount": 400}, {**EU, "id": "R-5", "amount": 1}]
    assert region_totals(records) == {"EU": {"accepted": 3, "gross": 501}}


def test_region_totals_ignores_records_the_validator_drops():
    """A dropped record contributes neither to ``accepted`` nor to ``gross``."""
    records = [
        NA,
        {**NA, "id": "R-6", "amount": -5},  # credits are rejected
        {**NA, "id": "R-7", "amount": True},  # bool is not a whole number
        {**NA, "id": "R-8", "currency": "GBP"},  # unknown currency
        {**NA, "id": "R-9", "region": "LATAM"},  # unknown region
    ]
    assert region_totals(records) == {"NA": {"accepted": 1, "gross": 250}}


def test_region_with_no_accepted_records_is_absent_not_zeroed():
    """The spec's headline case.

    ``EU`` appears in the feed, but every EU record is dropped. The key must be
    missing entirely — a zeroed ``{"accepted": 0, "gross": 0}`` entry is wrong,
    because a caller cannot tell it apart from a region that genuinely settled
    nothing.
    """
    records = [
        NA,
        {**EU, "id": "R-10", "amount": -1},
        {key: value for key, value in EU.items() if key != "id"},
    ]
    totals = region_totals(records)

    assert "EU" not in totals
    assert totals == {"NA": {"accepted": 1, "gross": 250}}


def test_region_totals_of_an_empty_feed_is_empty():
    assert region_totals([]) == {}


def test_region_totals_of_an_all_rejected_feed_is_empty():
    assert region_totals([{**EU, "amount": -1}, {**NA, "currency": "GBP"}]) == {}


def test_region_totals_keeps_a_zero_amount_record():
    """Zero is a valid gross, so the region is present with a zero ``gross``.

    This is the mirror of the absent-region rule: absence means *no accepted
    record*, not *nothing settled*.
    """
    totals = region_totals([{**APAC, "amount": 0}])
    assert totals == {"APAC": {"accepted": 1, "gross": 0}}


def test_region_totals_uses_integer_arithmetic():
    totals = region_totals([EU, {**EU, "id": "R-11", "amount": 3}])
    gross = totals["EU"]["gross"]
    assert isinstance(gross, int) and not isinstance(gross, bool)
    assert isinstance(totals["EU"]["accepted"], int)


def test_region_totals_does_not_mutate_the_input():
    records = [dict(EU), dict(NA)]
    before = [dict(record) for record in records]
    region_totals(records)
    assert records == before


def test_region_totals_is_idempotent():
    records = [EU, NA, {**NA, "id": "R-12", "amount": 50}]
    assert region_totals(records) == region_totals(records)


def test_region_totals_returns_a_plain_dict():
    """Not a defaultdict: a missing region must raise, never insert."""
    totals = region_totals([NA])
    assert type(totals) is dict
    assert "EU" not in totals
