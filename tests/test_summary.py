"""Tests for the four-figure reconciliation summary.

Every expected value below is derived by hand from the feed contract and the
existing helpers, and written in as a literal with its arithmetic in a comment.
No test asserts "whatever reconciliation_summary() returned" — a test that
encodes the number the implementation produced cannot report that the number is
wrong, which is how an earlier attempt at this module passed a green suite while
two of its four figures were incorrect.

Derivation of the committed feed's figures, from data/records.json and
data/rates.json (rates are basis points against USD; to_usd_cents() floors):

    id       amount  ccy  region  gross c   fee (local)  fee c   net c
    R-1001     1200  EUR  EU       132000   25+180=205   22550  109450
    R-1002      450  USD  NA        45000   25+ 22= 47    4700   40300
    R-1003     9800  JPY  APAC       6566   25+  0= 25      16    6549
    R-1004       10  USD  NA         1000   25+  0= 25    2500   -1500
    R-1005     2750  USD  EU       275000   25+412=437   43700  231300
                                   ------                -----  ------
                              G =  459566          F =  73466  N = 386099

Three rows are rejected: "Fennel Labs" has no id, R-1007 is GBP (not in
CURRENCY_CODES), R-1008's amount is the string "n/a". Note check_record() does
NOT enforce ALLOWED_PAIRS, so R-1005 (EU/USD) is accepted.

    effective_fee_bp = 73466 * 10000 // 459566 = 1598   (of GROSS settled value)
    settled_dollars  = (386099 + 50) // 100    = 3861   (SETTLED, i.e. net)
    largest_share_bp = 231300 * 10000 // 386099 = 5990  (net over net)
    rejected                                    = 3
"""

from __future__ import annotations

import copy

from src.records import load_records
from src.summary import reconciliation_summary

# A record that clears the feed contract, for hand-built lists to vary from.
CLEAN = {
    "id": "H-1",
    "name": "Hand Built",
    "amount": 1000,
    "currency": "USD",
    "region": "NA",
}


def test_committed_feed_returns_the_four_figures():
    # See the module docstring for the full per-record derivation.
    assert reconciliation_summary() == {
        "effective_fee_bp": 1598,
        "settled_dollars": 3861,
        "largest_share_bp": 5990,
        "rejected": 3,
    }


def test_records_defaults_to_the_committed_feed():
    # The default argument must be the committed feed, not some other source.
    assert reconciliation_summary() == reconciliation_summary(load_records())


def test_single_record_settles_its_whole_net_value():
    # fee = 25 + 1000 * 500 // 10000 = 75; gross 100000c, fee 7500c, net 92500c.
    #   effective_fee_bp = 7500 * 10000 // 100000 = 750
    #   settled_dollars  = (92500 + 50) // 100    = 925
    #   largest_share_bp = 92500 * 10000 // 92500 = 10000  (the only record)
    assert reconciliation_summary([dict(CLEAN)]) == {
        "effective_fee_bp": 750,
        "settled_dollars": 925,
        "largest_share_bp": 10000,
        "rejected": 0,
    }


def test_a_rejected_record_is_counted_but_never_valued():
    # GBP is not in CURRENCY_CODES, so the second row is dropped by the feed
    # contract. Every figure but `rejected` must be identical to the single
    # accepted record above -- the dropped row contributes no value anywhere.
    rows = [dict(CLEAN), {**CLEAN, "id": "H-2", "currency": "GBP", "region": "EU"}]
    assert reconciliation_summary(rows) == {
        "effective_fee_bp": 750,
        "settled_dollars": 925,
        "largest_share_bp": 10000,
        "rejected": 1,
    }


def test_a_fee_larger_than_the_amount_settles_negative():
    # amount 10 USD/NA: fee = 25 + 10 * 500 // 10000 = 25, so net = -15 local.
    #   gross 1000c, fee 2500c, net -1500c
    #   effective_fee_bp = 2500 * 10000 // 1000  = 25000  (fees exceed gross)
    #   settled_dollars  = -((1500 + 50) // 100) = -15
    #   largest_share_bp = -1500 * 10000 // -1500 = 10000 (both signs cancel)
    assert reconciliation_summary([{**CLEAN, "amount": 10}]) == {
        "effective_fee_bp": 25000,
        "settled_dollars": -15,
        "largest_share_bp": 10000,
        "rejected": 0,
    }


def test_an_empty_feed_returns_zeros_rather_than_raising():
    assert reconciliation_summary([]) == {
        "effective_fee_bp": 0,
        "settled_dollars": 0,
        "largest_share_bp": 0,
        "rejected": 0,
    }


def test_a_zero_amount_record_still_has_a_defined_share():
    # check_record() accepts amount == 0 (only negatives are rejected -- see
    # tests/test_validate.py::test_check_record_rejects_a_negative_amount), and
    # such a record grosses nothing while still bearing the flat fee:
    #   gross = 0 * 10000 // 100      = 0      -> G == 0
    #   fee   = 25 + 0 * 500 // 10000 = 25     -> F = 25 * 10000 // 100 = 2500c
    #   net   = 0 - 25 = -25 local             -> N = -2500c, so N != 0
    #
    # effective_fee_bp has no denominator and is 0. largest_share_bp DOES have
    # one: -2500 * 10000 // -2500 = 10000, that record being the whole of the
    # settled value. A guard written per-feed ("G == 0 or N == 0 -> both are 0")
    # returns 0 here and fails this assertion; the guard must be per-denominator.
    assert reconciliation_summary([{**CLEAN, "amount": 0}]) == {
        "effective_fee_bp": 0,
        "settled_dollars": -25,
        "largest_share_bp": 10000,
        "rejected": 0,
    }


def test_a_negative_share_truncates_toward_zero_rather_than_flooring():
    # One earner outweighed by fee-only records, so the largest single net is
    # positive while the feed as a whole settles negative.
    #   JPY 9800 APAC: fee 25, net 9775 local -> 9775 * 67 // 100 =  6549c
    #   three USD/NA amount=0 records         ->                    -2500c each
    #   G = 9800 * 67 // 100 = 6566;  F = 16 + 3 * 2500 = 7516
    #   N = 6549 - 7500 = -951;  largest = 6549
    #
    #   effective_fee_bp = 7516 * 10000 // 6566   = 11446
    #   settled_dollars  = -((951 + 50) // 100)   = -10        (-9.51)
    #   largest_share_bp = 6549 * 10000 / -951    = -68864.35...
    #                    -> -68864 truncated toward zero.
    # Plain `//` floors to -68865 and fails this assertion.
    rows = [{"id": "J-1", "name": "Jay", "amount": 9800, "currency": "JPY", "region": "APAC"}]
    rows += [{**CLEAN, "id": f"Z-{index}", "amount": 0} for index in range(3)]
    assert reconciliation_summary(rows) == {
        "effective_fee_bp": 11446,
        "settled_dollars": -10,
        "largest_share_bp": -68864,
        "rejected": 0,
    }


def test_a_positive_half_cent_rounds_away_from_zero():
    # JPY 100 APAC: fee 25, net 75 local -> 75 * 67 // 100 = 50c, exactly $0.50.
    # Half away from zero gives 1. Python's round() is banker's rounding and
    # gives 0 here; truncation also gives 0. Only this test distinguishes them.
    #   G = 100 * 67 // 100 = 67;  F = 25 * 67 // 100 = 16
    #   effective_fee_bp = 16 * 10000 // 67 = 2388
    rows = [{"id": "J-2", "name": "Jay", "amount": 100, "currency": "JPY", "region": "APAC"}]
    assert reconciliation_summary(rows) == {
        "effective_fee_bp": 2388,
        "settled_dollars": 1,
        "largest_share_bp": 10000,
        "rejected": 0,
    }


def test_a_negative_half_cent_rounds_away_from_zero():
    # The issue's own worked example: -0.5 goes to -1, not to 0.
    #   JPY 100 APAC (as above)        -> net   50c
    #   USD/NA 25: fee = 25 + 25 * 500 // 10000 = 26, net -1 local -> -100c
    #   N = 50 - 100 = -50c, exactly -$0.50 -> settled_dollars = -1
    #   G = 67 + 2500 = 2567;  F = 16 + 2600 = 2616
    #   effective_fee_bp = 2616 * 10000 // 2567   = 10190
    #   largest_share_bp = 50 * 10000 // -50      = -10000
    rows = [
        {"id": "J-2", "name": "Jay", "amount": 100, "currency": "JPY", "region": "APAC"},
        {**CLEAN, "id": "U-1", "amount": 25},
    ]
    assert reconciliation_summary(rows) == {
        "effective_fee_bp": 10190,
        "settled_dollars": -1,
        "largest_share_bp": -10000,
        "rejected": 0,
    }


def test_every_figure_is_a_plain_integer():
    # Money is integer arithmetic end to end. `type(...) is int` rather than
    # isinstance() so that a bool -- an int subclass, which the validator
    # already guards against in amounts -- fails too.
    #
    # Limit worth stating: this catches a float REACHING the result, not a float
    # intermediate that happens to land on a whole number. The no-float-
    # intermediate rule is enforced by construction in src/summary.py (no `/`,
    # no round(), no float()) and by reading the diff, not by this assertion.
    for value in reconciliation_summary().values():
        assert type(value) is int


def test_malformed_rows_are_rejected_rather_than_raising():
    # A feed row is free-form JSON and is not guaranteed to be a dict.
    # check_record() screens every one of these, so they count as rejected and
    # none of them reaches the arithmetic: the three value figures are identical
    # to the single-accepted-record case.
    rows = [None, "nope", 42, {}, dict(CLEAN)]
    assert reconciliation_summary(rows) == {
        "effective_fee_bp": 750,
        "settled_dollars": 925,
        "largest_share_bp": 10000,
        "rejected": 4,
    }


def test_the_summary_is_idempotent_and_does_not_mutate_its_input():
    rows = [dict(CLEAN), {**CLEAN, "id": "H-2", "amount": 0}]
    before = copy.deepcopy(rows)

    first = reconciliation_summary(rows)
    second = reconciliation_summary(rows)

    assert first == second
    assert rows == before
