# Plan — issue #59, settlement reconciliation total

## What "total settled value, net of fees" means here

Reading `CLAUDE.md`'s layout table and the actual code (not just the docstrings):

- **"the feed contract"** is `src.validate.check_record()` — literally named as such in
  `CLAUDE.md` ("`src/validate.py` | the feed contract — `check_record()` returns a normalised
  copy or `None`"). I re-read `check_record()` in full: it drops a row for a missing validated
  field, an unrecognised region, an unrecognised currency, a non-int-or-bool amount, or a
  negative amount. **It does not currently cross-check region against currency using
  `ALLOWED_PAIRS`**, despite the module docstring's claim that it does — `ALLOWED_PAIRS` is
  referenced only by `report.py` for a display line and by
  `tests/test_validate.py::test_settlement_pairs_are_configured` (which only checks the tuple's
  contents, not that anything enforces them). I confirmed this against the committed feed: record
  `R-1005` is region `EU` / currency `USD`, which is not in `ALLOWED_PAIRS`, and it is still one
  of the 5 accepted records per `tests/test_pipeline.py::test_summarise_counts_the_feed_it_was_given`
  and the golden artifact. Since the issue says not to modify any existing module, `reconcile.py`
  will call `check_record()` as it actually behaves today, not as its docstring aspires to behave.
  I will **not** add my own `ALLOWED_PAIRS` re-check in `reconcile.py` — that would silently
  diverge from what every other consumer of the feed (`report.py`, `summarise.py`) treats as
  "accepted."
- **"the fee schedule has been charged against them"** is `src.normalise.apply_fees()`, which
  returns each accepted record plus a `net` field: `net = amount - fee_for(record)`, computed in
  the record's *original currency units* (not cents) — confirmed by
  `tests/test_pipeline.py::test_apply_fees_charges_the_regional_handling_rate` and by the golden
  artifact's "Net after fees" block (e.g. `R-1004` nets to `-15`: a flat fee can exceed a small
  gross amount, and `apply_fees` permits a negative net — it only guards against a negative
  *gross*).
- Converting to USD cents is `src.rates.to_usd_cents(amount, currency)`, which already does
  `amount * rate // 100` in pure integer arithmetic and returns `0` if a currency has no rate
  (defensive default already in the module — not something I add).

So the pipeline `settlement_total_cents()` runs is:

```
raw records
  -> check_record()      (the feed contract: drop what it drops, normalise what it keeps)
  -> apply_fees()         (adds "net" = amount - fee, in currency units, per record)
  -> to_usd_cents(net, currency)   (per record, converts the NET amount, not the gross)
  -> sum()
```

This differs from `report.py`'s "Total (USD)" line, which sums `to_usd_cents(amount, ...)` on
the **gross** amount (pre-fee) — that line is a different, already-existing figure and is out of
scope; the issue explicitly asks for a *new* number that nothing today renders ("nothing states
what the feed settles to in total"). I will not touch `report.py` or the golden artifact.

## New file: `src/reconcile.py`

```python
"""Settlement reconciliation total: what the feed nets to, in USD cents."""

from __future__ import annotations

from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.validate import check_record


def settlement_total_cents(records: list[dict] | None = None) -> int:
    """Return the feed's total settled value, in whole USD cents, net of fees.

    *records* defaults to the committed feed. Each record is passed through
    the feed contract (``check_record``) before anything else runs, so a
    malformed or rejected row contributes nothing rather than raising —
    ``apply_fees`` and ``to_usd_cents`` are only ever given normalised rows.
    """
    raw = load_records() if records is None else records
    accepted = [checked for checked in (check_record(row) for row in raw) if checked]
    settled = apply_fees(accepted)
    return sum(to_usd_cents(row["net"], row["currency"]) for row in settled)
```

Notes on why this is robust/complete against the repo's definitions:

- `records=None` and `records=[]` both work: `load_records()` for the former, and
  `sum()` over an empty list is `0` for the latter — no special-casing needed.
- Every element the function ever hands to `apply_fees`/`to_usd_cents` has already passed
  `check_record`, so it is guaranteed to carry `amount` (non-negative int), `currency` (one of
  `CURRENCY_CODES`), and `region` — the same guarantee `report.py` relies on. A record that is
  not a dict, or missing a field, or carrying a bool/negative amount, is dropped before it can
  raise inside `apply_fees` (which only guards the negative-gross case) or `to_usd_cents`.
  Malformed input degrades to "contributes zero," not a crash.
  the raw `records` argument itself not being a list (e.g. `None`-but-not-really, a generator) is
  not specially guarded — `load_records()` already returns `list[dict]`, and the signature
  documents `list[dict] | None`, matching every other function in this codebase (`summarise()`,
  `render_report()`) which likewise assume a list and do not defensively check its type.
- Integer arithmetic end to end: `check_record` only accepts `int` (non-bool) amounts,
  `apply_fees` does integer subtraction, `to_usd_cents` does integer `*` and `//`. No float ever
  enters the computation.
- Idempotent: calling it twice with the same input list produces the same total (nothing here
  mutates its input — `check_record` and `apply_fees` both return fresh copies).

## Expected value for the committed feed

I hand-computed this from the golden artifact's "Net after fees" figures (`R-1001: 995 EUR`,
`R-1002: 403 USD`, `R-1003: 9775 JPY`, `R-1004: -15 USD`, `R-1005: 2313 USD`) and
`data/rates.json` (`USD: 10000, EUR: 11000, JPY: 67`), converting each net amount to USD cents
with the same `amount * rate // 100` integer formula `to_usd_cents` uses, via
`python3 -c "print(...)"` (not by hand):

| record | net (currency units) | currency | to_usd_cents |
|---|---|---|---|
| R-1001 | 995 | EUR | 109450 |
| R-1002 | 403 | USD | 40300 |
| R-1003 | 9775 | JPY | 6549 |
| R-1004 | -15 | USD | -1500 |
| R-1005 | 2313 | USD | 231300 |

Sum = **386099** (i.e. $3,860.99). `tests/test_reconcile.py` will assert
`settlement_total_cents() == 386099` for the committed feed, and I will re-derive this same
number independently at implementation time by actually running the function, not just trusting
this hand trace — if the two disagree I'll treat the running code as ground truth and re-check my
trace rather than adjust the assertion to match a mistaken run.

## New file: `tests/test_reconcile.py`

- `test_settlement_total_cents_matches_the_committed_feed` — asserts the exact total above for
  the default (`records=None`) call.
- `test_settlement_total_cents_over_a_hand_built_feed` — a single clean `NA`/`USD` record with a
  known amount, asserting the exact expected cents (gross, minus flat + handling fee, converted
  at the committed USD rate).
- `test_settlement_total_cents_sums_multiple_records` — two or three hand-built accepted records
  across different currencies, asserting the sum equals the sum of each one's independently
  computed contribution (cross-checks that the function doesn't do anything per-record-order
  dependent).
- `test_settlement_total_cents_skips_rejected_records` — a hand-built list mixing one accepted
  record with one that the feed contract drops (e.g. missing `id`, or a boolean amount, or a
  negative amount, or an unrecognised currency), asserting the rejected row contributes nothing
  (total equals the accepted row's contribution alone).
- `test_settlement_total_cents_of_an_empty_feed_is_zero` — `settlement_total_cents([]) == 0`.

All expected values in these tests will be computed via `python3 -c "print(...)"` per the repo's
math-verification convention, not worked out by hand in my head, before being written into the
assertions.

## Files touched

- **Add** `src/reconcile.py` (new module, per issue scope).
- **Add** `tests/test_reconcile.py` (new test file, per issue scope).
- Nothing else. No existing module, `TESTING.md` row, or the golden artifact is touched.
  (`TESTING.md`'s routing table technically goes stale by omission — it won't list the new
  `reconcile` area — but the issue does not ask for a `TESTING.md` update and that file isn't an
  "existing module" whose behavior changes, so I'm leaving it alone rather than expanding scope
  unprompted. I'll call this out explicitly again in the PR description.)

## Gates I will run before declaring done

```
python -m compileall -q src
python -m ruff check .
python -m pytest -q
```

Expected: 31 existing passes + the new `test_reconcile.py` cases, 0 skipped, with
`FACTORY_TESTBED_FLAKE` left unset.
