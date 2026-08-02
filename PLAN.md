# PLAN — Issue #8: Split the fee calculation into its two components

## Re-measurement of the issue against real code

Read `src/normalise.py` in full (32 lines). Current `fee_for()`:

```python
FLAT_FEE = 25
HANDLING_BP = {"EU": 1500, "NA": 500, "APAC": 0}

def fee_for(record: dict) -> int:
    """Return the total fee charged against *record*."""
    return FLAT_FEE + record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000
```

The issue's claim — "computes the flat fee and the regional handling charge in a single
expression" — is accurate. `fee_for()` has exactly one caller, `apply_fees()` (line 29,
`row["net"] = record["amount"] - fee_for(record)`), and no other file in `src/` or `tests/`
references `fee_for`, `FLAT_FEE`, or `HANDLING_BP` by name (checked with `grep -rn` across
`src/` and `tests/`).

**Correction (CP1 gate finding, EXECUTED):** only one existing test actually reaches
`fee_for()` — `test_apply_fees_charges_the_regional_handling_rate`. The other fee-adjacent test,
`test_apply_fees_rejects_a_negative_gross_amount`, exercises the negative-amount guard in
`apply_fees()` (`src/normalise.py:22-24`) and raises `ValueError` before the loop that calls
`fee_for()` (line 29) is ever reached, so it never touches fee calculation at all. Neither test
imports `fee_for` directly, so splitting it into private helpers changes no test's import
surface, but only one of the two provides any indirect coverage of the arithmetic being split.

**Verdict: the issue is correct as written. Nothing to correct.**

## Operator-precedence note (why this matters for "identical value")

`*` and `//` are the same precedence in Python and left-associative, so the current expression
parses as `FLAT_FEE + ((record["amount"] * HANDLING_BP.get(record["region"], 0)) // 10000)` —
i.e. the multiply happens *before* the floor-division, not `amount * (bp // 10000)`. The new
`_handling_component()` must reproduce `amount * bp // 10000` exactly (multiply-then-floor-div
in one expression), not split further into `bp // 10000` first, or results would diverge for
non-exact-division cases.

## Change

File: `src/normalise.py`

Add two private helpers immediately above `fee_for()`, and rewrite `fee_for()` to sum them:

```python
def _flat_component(record: dict) -> int:
    """Return the flat portion of the fee for *record*."""
    return FLAT_FEE


def _handling_component(record: dict) -> int:
    """Return the regional handling portion of the fee for *record*."""
    return record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000


def fee_for(record: dict) -> int:
    """Return the total fee charged against *record*."""
    return _flat_component(record) + _handling_component(record)
```

Both helpers take `record: dict` (even though `_flat_component` ignores it) so the two have a
matching signature and either could later be swapped for a per-record flat fee without changing
call sites — this is a judgment call in service of "no public name changes / minimal surface",
not a requirement from the issue; flagging it as a design choice rather than a spec requirement.

`apply_fees()` (lines 16–31) is untouched — it already calls `fee_for(record)` at line 29 and
needs no change.

No other file imports or calls `fee_for`, `FLAT_FEE`, or `HANDLING_BP`, so no caller-side changes
are needed anywhere else in `src/` or `tests/`.

## Why this preserves behaviour exactly

- `_flat_component()` returns `FLAT_FEE` unconditionally — same constant, same value, for every
  input, including a record with a missing `region` key (it never touches `record["region"]`
  itself, so it cannot raise on that key's absence).
- `_handling_component()` is a verbatim extraction of the existing right-hand subexpression,
  same operator order (`*` then `//`), same `.get(..., 0)` default for an *unknown* region value.
  **Correction (CP1 gate finding, EXECUTED):** a *missing* `region` key is not covered by that
  default — `record["region"]` is evaluated as a plain subscript before `.get` ever runs, so a
  record without a `region` key raises `KeyError` today, and must keep raising `KeyError` after
  the split. This is current behaviour and the issue requires `fee_for()` to return an identical
  value (or raise identically) for every input it accepts today, so no `.get("region", ...)`
  guard is added around the key lookup itself — only the *value* returned by that lookup goes
  through `HANDLING_BP.get(..., 0)` for unknown-but-present regions, exactly as today.
- `fee_for()`'s new body (`_flat_component(record) + _handling_component(record)`) is
  algebraically identical to the old body (`FLAT_FEE + record["amount"] * HANDLING_BP.get(...) //
  10000`) for every input, by associativity of integer `+` — no reordering of the multiply/divide
  changes.
- Since `fee_for()`'s output is unchanged for all inputs, `apply_fees()`'s output (`net`) is
  unchanged, and everything downstream (`src/summarise.py`, `src/report.py`,
  `artifacts/report.golden.txt`) is unaffected. No `python -m tools.write_golden` regeneration is
  needed or will be run.
- Both new helpers are private (leading underscore) — no public name changes, satisfying the
  issue's explicit constraint.

## Testing plan (per TESTING.md routing)

This change is confined to `src/normalise.py` (the "fees" row), routed to
`tests/test_pipeline.py`. Per declared verification depth **A**, I will:

1. Run the existing suite unchanged first to confirm the 31-passed baseline still holds after the
   edit (no test should need modification since behaviour is unchanged and no public names moved).
2. Add one new unit test directly against the private helpers (per Verification Protocol's
   "write the test, then break the thing it tests" requirement — the refactor itself has no
   behavioural test today, only indirect coverage via `apply_fees()`), e.g. in
   `tests/test_pipeline.py`:
   - `test_flat_and_handling_components_sum_to_fee_for` — asserts
     `_flat_component(record) + _handling_component(record) == fee_for(record)` for a sample
     record, and asserts `_flat_component(record) == FLAT_FEE` and
     `_handling_component(record) == record["amount"] * HANDLING_BP[record["region"]] // 10000`
     for an EU record with a non-exact-division amount (e.g. `amount=999`, `region="EU"`, so
     `999 * 1500 // 10000 = 149` rather than a round number) to pin the operator-order behaviour
     called out above.
   - Mutation check: temporarily change `_handling_component` to `bp // 10000 * amount` (breaks
     the multiply/floor-div order for non-exact cases) or drop `_flat_component`'s contribution,
     confirm the new test fails, then revert.
3. Run gates: `python -m compileall -q src`, `python -m ruff check .`,
   `python -m pytest -q` (full suite, since depth A and the change is small — full run stays
   cheap).

## Files/functions touched

- `src/normalise.py`: add `_flat_component(record)`, `_handling_component(record)`; rewrite
  `fee_for(record)` body to `return _flat_component(record) + _handling_component(record)`.
  `FLAT_FEE`, `HANDLING_BP`, `apply_fees()` unchanged.
- `tests/test_pipeline.py`: add one new test function covering the two new private helpers.

No changes to `src/report.py`, `artifacts/report.golden.txt`, `tools/write_golden.py`, or any
other module.
