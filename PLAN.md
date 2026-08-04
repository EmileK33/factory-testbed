# PLAN — `src/summary.py::reconciliation_summary()`

## Source of truth re-read

- `src/records.py` (`load_records`) — feed loader, returns fresh dicts, defaults to
  `data/records.json`.
- `src/validate.py` (`check_record`, `ALLOWED_PAIRS`) — **`check_record` does NOT enforce
  `ALLOWED_PAIRS`.** It only checks: required fields present, `region` in `REGION_CODES`,
  `currency` in `CURRENCY_CODES`, `amount` a non-bool whole number, `amount >= 0`. `ALLOWED_PAIRS`
  is exported purely for `report.py`'s footer text. Confirmed against
  `tests/test_pipeline.py::test_summarise_counts_the_feed_it_was_given`, which asserts
  `accepted == 5` and `rejected == ["<unlabelled>", "R-1007", "R-1008"]` for the committed feed —
  i.e. `R-1005` (region `EU`, currency `USD`, a pair not in `ALLOWED_PAIRS`) is **accepted**. My
  first pass wrongly assumed the pair check was part of acceptance; re-reading the code and the
  existing test caught it. "Settled" in this plan = "accepted" = `check_record(record) is not
  None`.
- `src/normalise.py` (`fee_for`, `FLAT_FEE`, `HANDLING_BP`) — `fee_for(record)` returns the fee in
  the record's **native currency, whole units** (same unit as `record["amount"]`, not cents).
  `apply_fees` calls `fee_for` on the native amount before any currency conversion; conversion
  never happens inside `normalise.py`.
- `src/rates.py` (`to_usd_cents`) — converts a whole-unit native amount to whole USD cents via
  `amount * rate // 100`, floor division. Returns `0` if the currency has no rate (not reachable
  for accepted records today, since `CURRENCY_CODES` ⊆ keys of `data/rates.json`, but the helper
  itself tolerates it).
- `src/report.py` — shows the established pattern this module mirrors: filter raw records through
  `check_record`, then `sum(to_usd_cents(row["amount"], row["currency"]) for row in accepted)` for
  a gross USD-cents total. `src/summary.py` reuses that same pattern rather than inventing a new
  one.
- Issue #62 (full text re-read) — four integer keys, non-negotiable conventions: integer
  arithmetic end to end, no float anywhere including intermediates; basis-point figures truncated
  toward zero; `settled_dollars` rounded half away from zero; currency conversion per record via
  the existing rate helper; do not modify existing modules.

## Definitions used throughout

- `raw` = `records` if given, else `load_records()`.
- `accepted` = `[a for r in raw if (a := check_record(r)) is not None]`.
- `gross_cents(row)` = `to_usd_cents(row["amount"], row["currency"])` — the record's settled value
  in whole USD cents, **before** any fee is deducted.
- `fee_cents(row)` = `to_usd_cents(fee_for(row), row["currency"])` — the fee is computed first, in
  the record's native currency (via the existing `fee_for`, unmodified), *then* that fee amount is
  run through the same per-record conversion helper used for the gross amount. Fee application
  precedes currency conversion; both conversions happen independently per record — no aggregation
  ever crosses a currency boundary before conversion.
- `total_gross_cents` = `sum(gross_cents(row) for row in accepted)`.
- `total_fee_cents` = `sum(fee_cents(row) for row in accepted)`.

All of `gross_cents`, `fee_cents`, `total_gross_cents`, `total_fee_cents` are `>= 0`, because
`check_record` rejects any negative `amount`, `FLAT_FEE` (25) and `HANDLING_BP` (0/500/1500) are
both non-negative constants, and `to_usd_cents` multiplies non-negative operands. Given that, floor
division (`//`) and "truncate toward zero" coincide for every ratio below, so plain `//` is
correct — no `math.trunc`/`int()` float path is needed or used.

## The four figures

### 1. `effective_fee_bp`

- **Numerator:** `total_fee_cents`.
- **Denominator:** `total_gross_cents`.
- **Fee vs. conversion order:** fee first (native currency, via `fee_for`), conversion second (per
  record, via `to_usd_cents`) — see `fee_cents()` above.
- **Truncation:** two points. (a) `to_usd_cents` itself floors on every call (inherited, not
  reimplemented). (b) the final ratio: `total_fee_cents * 10000 // total_gross_cents`, floored —
  equivalent to truncation toward zero since both operands are `>= 0`.
- **Edge case:** if `total_gross_cents == 0` (empty feed, or every record's amount converts to `0`
  cents), the ratio is undefined by division; return `0` rather than raising, so the summary
  degrades gracefully instead of aborting (per the repo's fault-tolerance expectation).

### 2. `settled_dollars`

- **Numerator:** `total_gross_cents` (gross, i.e. before fees — the fee load is reported
  separately via `effective_fee_bp`, so this figure is not double-counting or net-of-fee).
- **Denominator:** fixed `100` (cents per dollar).
- **Conversion order:** currency conversion already folded into `total_gross_cents` per record; no
  fee involved in this figure at all.
- **Rounding:** half away from zero, applied exactly once, at the cents-to-dollars step (never
  earlier — every intermediate stays in whole cents). Implemented without floats:
  ```python
  def _round_half_away_from_zero(cents: int) -> int:
      if cents >= 0:
          return (cents + 50) // 100
      return -((-cents + 50) // 100)
  ```
  Verified against the issue's own example: `_round_half_away_from_zero(-50) == -1` (i.e. -0.50 →
  -1, not 0). `total_gross_cents` is `>= 0` for every record the current contract can accept, so
  the negative branch is currently unreachable from `reconciliation_summary()`'s own call site —
  but it is implemented and will be unit-tested directly (not just through the committed feed),
  since the issue calls the negative case out by name and a future contract change (e.g. credits)
  must not silently regress it.

### 3. `largest_share_bp`

- **Numerator:** `largest_cents = max((gross_cents(row) for row in accepted), default=0)` — the
  single largest **settled** (accepted) record's USD-cents value, compared post-conversion so
  records in different currencies are commensurable.
- **Denominator:** `total_gross_cents`.
- **Conversion order:** conversion happens per record before the `max()` comparison; no fee
  involved.
- **Truncation:** `largest_cents * 10000 // total_gross_cents`, floored (== truncation toward zero,
  non-negative operands).
- **Edge case:** if `total_gross_cents == 0`, return `0` (same reasoning as `effective_fee_bp`).

### 4. `rejected`

- Pure count, no ratio: `len(raw) - len(accepted)`. Equivalent to counting records where
  `check_record(record) is None`; the subtraction form avoids iterating twice.

## Expected result for the committed feed (`data/records.json`)

Recomputed by hand-simulating the exact algorithm above in a throwaway Python snippet (not part of
the shipped code) to cross-check before implementation:

- Accepted (settled): `R-1001, R-1002, R-1003, R-1004, R-1005` (5 of 8) — matches
  `tests/test_pipeline.py`'s existing assertion of `accepted == 5`.
- `total_gross_cents = 459566`, `total_fee_cents = 73466`, `largest_cents = 275000` (`R-1005`,
  2750 USD → EU handling fee of 437 USD → still the largest gross record).
- `effective_fee_bp = 73466 * 10000 // 459566 = 1598`
- `settled_dollars = round_half_away_from_zero(459566) = 4596`
- `largest_share_bp = 275000 * 10000 // 459566 = 5983`
- `rejected = 3`

So `reconciliation_summary()` with no arguments is expected to return:

```python
{
    "effective_fee_bp": 1598,
    "settled_dollars": 4596,
    "largest_share_bp": 5983,
    "rejected": 3,
}
```

## Implementation shape (no code yet)

`src/summary.py` will import `check_record` from `src.validate`, `fee_for` from `src.normalise`,
`to_usd_cents` from `src.rates`, and `load_records` from `src.records` — no existing module is
edited. One private rounding helper (`_round_half_away_from_zero`) plus the public
`reconciliation_summary(records: list[dict] | None = None) -> dict`.

`tests/test_summary.py` will assert:
1. The exact four-key dict above for the committed feed (`reconciliation_summary()` with no args).
2. At least two hand-built record lists — planned cases: (a) a small multi-currency list to
   exercise the per-record conversion/fee/truncation path with a hand-checked expected dict, and
   (b) an all-rejected or empty list to exercise the `total_gross_cents == 0` branch, asserting
   `effective_fee_bp == 0` and `largest_share_bp == 0` rather than a `ZeroDivisionError`. A third
   case will directly unit-test `_round_half_away_from_zero` (or the rounding behavior through a
   crafted record set) on a negative/half-cent boundary, since that path is unreachable from the
   committed feed but is explicitly required by the issue.

## Gaps found against Complete / Robust / Fault-tolerant and folded in above

- **Complete:** zero-accepted-records path (all four figures still well-defined; `rejected` always
  is, the other three needed the `default=0` / `total_gross_cents == 0` guards above).
- **Robust:** rounding helper handles negative cents correctly even though today's contract can't
  produce a negative `total_gross_cents` — implemented and tested directly rather than left
  implicit.
- **Fault-tolerant:** division-by-zero on an empty/degenerate settled set returns `0` instead of
  raising, so a caller building a dashboard from this summary doesn't crash on a feed that happens
  to reject everything.

Awaiting go-ahead before writing `src/summary.py` / `tests/test_summary.py`.
