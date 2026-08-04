"""Tests for the settlement reconciliation total."""

from __future__ import annotations

from src.reconcile import settlement_total_cents

# A single, cleanly accepted NA/USD record. Fee = FLAT_FEE (25) + 500bp of the
# gross (1000 * 500 // 10000 = 50), so net = 1000 - 75 = 925 USD, which
# converts to 92500 USD cents at the committed USD rate (10000 == 1.00).
SINGLE_RECORD = [
    {
        "id": "X-1",
        "name": "Test Co",
        "amount": 1000,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
]

# A second, independent accepted EU/EUR record. Fee = 25 + 1500bp of 500
# (500 * 1500 // 10000 = 75), so net = 500 - 100 = 400 EUR, which converts to
# 400 * 11000 // 100 = 44000 USD cents.
SECOND_RECORD = {
    "id": "X-2",
    "name": "Euro Co",
    "amount": 500,
    "currency": "EUR",
    "region": "EU",
    "tags": "",
}


def test_settlement_total_cents_matches_the_committed_feed():
    # Traced by hand from the golden artifact's "Net after fees" figures
    # (995 EUR, 403 USD, 9775 JPY, -15 USD, 2313 USD) converted at the
    # committed rates (USD 10000, EUR 11000, JPY 67) with the same
    # amount * rate // 100 integer formula src.rates.to_usd_cents uses, and
    # confirmed by actually running settlement_total_cents() against the
    # committed feed.
    assert settlement_total_cents() == 386099


def test_settlement_total_cents_over_a_hand_built_feed():
    assert settlement_total_cents(SINGLE_RECORD) == 92500


def test_settlement_total_cents_sums_multiple_records():
    combined = settlement_total_cents([SINGLE_RECORD[0], SECOND_RECORD])
    separately = settlement_total_cents(SINGLE_RECORD) + settlement_total_cents(
        [SECOND_RECORD]
    )
    assert combined == separately == 136500


def test_settlement_total_cents_skips_records_the_feed_contract_rejects():
    unlabelled = {
        "name": "No Id Co",
        "amount": 500,
        "currency": "USD",
        "region": "NA",
        "tags": "",
    }
    mixed = [SINGLE_RECORD[0], unlabelled]
    # The unlabelled record is dropped by check_record() (no "id"), so it
    # contributes nothing: the mixed total equals the single accepted row's
    # total on its own.
    assert settlement_total_cents(mixed) == settlement_total_cents(SINGLE_RECORD) == 92500


def test_settlement_total_cents_of_an_empty_feed_is_zero():
    assert settlement_total_cents([]) == 0


def test_settlement_total_cents_of_none_input_defaults_to_the_committed_feed():
    assert settlement_total_cents(None) == settlement_total_cents()
