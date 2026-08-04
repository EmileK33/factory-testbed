"""Tests for the reconciliation summary."""

from src.summary import _round_half_away_from_zero, reconciliation_summary


def test_reconciliation_summary_matches_the_committed_feed():
    # Accepted (settled) for data/records.json: R-1001..R-1005 (5 of 8) --
    # check_record() does not enforce ALLOWED_PAIRS, so R-1005 (EU/USD) is
    # accepted despite that pair not being one report.py lists as "in force".
    # Rejected: the unlabelled row, R-1007 (currency GBP), R-1008 (amount "n/a").
    assert reconciliation_summary() == {
        "effective_fee_bp": 1598,
        "settled_dollars": 4596,
        "largest_share_bp": 5983,
        "rejected": 3,
    }


def test_reconciliation_summary_over_a_hand_built_multi_currency_feed():
    records = [
        {"id": "A1", "name": "Alpha", "amount": 1000, "currency": "USD", "region": "NA"},
        {"id": "A2", "name": "Bravo", "amount": 500, "currency": "EUR", "region": "EU"},
        # Rejected: missing currency.
        {"id": "A3", "name": "Charlie", "amount": 200, "currency": "", "region": "NA"},
    ]

    # A1: gross 1000*10000//100=100000c; fee_native=25+1000*500//10000=75;
    #     fee 75*10000//100=7500c.
    # A2: gross 500*11000//100=55000c; fee_native=25+500*1500//10000=100;
    #     fee 100*11000//100=11000c.
    # total_gross=155000c, total_fee=18500c, largest=100000c (A1).
    # effective_fee_bp = 18500*10000//155000 = 1193
    # largest_share_bp = 100000*10000//155000 = 6451
    # settled_dollars = round_half_away_from_zero(155000) = 1550
    assert reconciliation_summary(records) == {
        "effective_fee_bp": 1193,
        "settled_dollars": 1550,
        "largest_share_bp": 6451,
        "rejected": 1,
    }


def test_reconciliation_summary_degrades_gracefully_with_nothing_settled():
    records = [
        {"id": "B1", "name": "Bad currency", "amount": 100, "currency": "GBP", "region": "EU"},
        {"id": "B2", "name": "Bad amount", "amount": "n/a", "currency": "USD", "region": "NA"},
    ]

    # No record clears the feed contract, so total_gross_cents is 0. Division
    # is avoided rather than raising ZeroDivisionError; the ratio figures come
    # back 0 instead of aborting the caller's larger flow.
    assert reconciliation_summary(records) == {
        "effective_fee_bp": 0,
        "settled_dollars": 0,
        "largest_share_bp": 0,
        "rejected": 2,
    }

    assert reconciliation_summary([]) == {
        "effective_fee_bp": 0,
        "settled_dollars": 0,
        "largest_share_bp": 0,
        "rejected": 0,
    }


def test_round_half_away_from_zero_rounds_a_negative_half_cent_boundary_away_from_zero():
    # This exercises the rounding helper directly, not through
    # reconciliation_summary() -- the committed validator can never produce a
    # negative total_gross_cents, so the public function cannot reach this
    # branch today. See the docstring on _round_half_away_from_zero().
    assert _round_half_away_from_zero(-50) == -1
    assert _round_half_away_from_zero(50) == 1
    assert _round_half_away_from_zero(-49) == 0
    assert _round_half_away_from_zero(49) == 0
    assert _round_half_away_from_zero(0) == 0
