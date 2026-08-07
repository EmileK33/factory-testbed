# PLAN — Issue #176: Split fee calculation into two components

## Re-measured facts

- `src/normalise.py` (32 lines total). `fee_for()` (lines 11-13):
  ```python
  def fee_for(record: dict) -> int:
      """Return the total fee charged against *record*."""
      return FLAT_FEE + record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000
  ```
  Module constants: `FLAT_FEE = 25` (line 5), `HANDLING_BP = {"EU": 1500, "NA": 500, "APAC": 0}` (line 8).
- Python operator precedence: `*` and `//` bind tighter than `+` and are left-associative, so the
  existing expression already evaluates as `FLAT_FEE + ((record["amount"] * HANDLING_BP.get(...)) // 10000)`.
  This means a direct split into "flat" and "handling" terms reproduces the exact same integer
  arithmetic — no reordering risk, no float involved anywhere (`//` is integer floor division
  throughout).
- Only caller of `fee_for()` is `apply_fees()` (line 29), same file. `apply_fees()` is unchanged by
  this item.
- Only external caller of `apply_fees` is `src/report.py:72` (`render_report()`), which feeds
  `artifacts/report.golden.txt` (verified via `tests/test_golden.py`).
- Test coverage for this module: `tests/test_pipeline.py` (2 tests, both currently green) — per
  `TESTING.md`'s routing table, fees are "coupled to no data file". `tests/test_golden.py` and
  `tests/test_report.py` indirectly exercise `fee_for()` through `render_report()`.
- Ruff config (`ruff.toml`): `select = ["E4", "E7", "E9", "F", "I"]` — no `ARG` (unused-argument)
  rule enabled, so an unused `record` parameter would not be flagged even if a helper's signature
  carried it without using it.
- Baseline gate run before touching anything: `python -m compileall -q src` clean;
  `python -m pytest -q tests/test_pipeline.py tests/test_golden.py tests/test_report.py` → 8
  passed.
- No written spec beyond the issue body itself (`gh issue view 176`, matches the cached
  `tests/fixtures/t2/I2.md` verbatim) — treated as the specification. It states three invariants:
  (1) `fee_for()` returns identical values for every input it accepts today, (2)
  `artifacts/report.golden.txt` is byte-for-byte unchanged, (3) no public name changes.

## Change

In `src/normalise.py`, replace `fee_for()` with:

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

Both helpers take `record: dict` for a consistent, extractable-later signature even though
`_flat_component` doesn't use it today (unused-argument lint is not enabled, confirmed above, so
this is a style choice, not a lint risk). `_handling_component` keeps the multiply-then-floor-divide
in the same left-to-right order as the original expression, so the arithmetic is byte-identical for
every input, including edge cases already implicitly covered by existing behavior:
- unknown region → `HANDLING_BP.get(record["region"], 0)` still defaults to 0 (same `.get` call,
  unchanged).
- `record["amount"] == 0` → handling component is `0`, total is `FLAT_FEE`, same as today.
- negative amounts never reach `fee_for()` in the current pipeline because `apply_fees()` raises
  `ValueError` first (line 23-24) — that guard is untouched, out of scope, and not affected by
  this split.

No other file changes. `apply_fees()`, module constants, imports, and all public names are
untouched, satisfying "no public name changes."

## Tests

Add a new test to `tests/test_pipeline.py` (the file `TESTING.md` already routes fee changes to)
asserting the two helpers are separable and sum correctly, plus that `fee_for()` still equals the
old combined formula for a couple of inputs (covering a nonzero-handling region and the zero-bp
`APAC` region, i.e. the flat-only path):

```python
from src.normalise import HANDLING_BP, FLAT_FEE, _flat_component, _handling_component, fee_for


def test_fee_components_sum_to_the_total():
    record = {"id": "R-9", "amount": 1000, "region": "EU"}
    assert _flat_component(record) == FLAT_FEE
    assert _handling_component(record) == 150
    assert fee_for(record) == _flat_component(record) + _handling_component(record)


def test_fee_for_apac_is_flat_only():
    record = {"id": "R-1", "amount": 1000, "region": "APAC"}
    assert _handling_component(record) == 0
    assert fee_for(record) == FLAT_FEE
```

These import the private helpers directly (acceptable — same package, verifying the extraction
itself, which is the entire point of the issue). They will fail on the current (pre-refactor) code
with `ImportError`/`AttributeError` since `_flat_component`/`_handling_component` don't exist yet —
confirms the tests actually exercise the new code, not a pass-by-coincidence.

The two existing `tests/test_pipeline.py` tests and `tests/test_golden.py` /
`tests/test_report.py` are the regression net proving `fee_for()`'s output and the emitted artifact
are unchanged — no edits needed to those, they should pass unmodified.

## Verification plan

1. Confirm new tests fail against current `fee_for()` (helpers don't exist) — proves they're real.
2. Apply the code change.
3. Re-run new tests → pass.
4. Full gate: `python -m compileall -q src`, `python -m ruff check .`, `python -m pytest -q`.
5. Explicitly diff `artifacts/report.golden.txt` against a fresh `python -m tools.write_golden`
   dry-run output (or just rely on `tests/test_golden.py`, which byte-compares) to directly confirm
   invariant (2) from the issue, not just infer it from tests passing.

## Scope / non-goals

- Not touching `apply_fees()`, `src/report.py`, `src/rates.py`, or any data files.
- Not changing `FLAT_FEE` or `HANDLING_BP` values or types.
- Not adding public exports of the new helpers (they stay `_`-prefixed/private, per the issue).

🔍 CP1 — re-read: `src/normalise.py` (full file, 32 lines) and `src/report.py`'s call site
(line 72) and `tests/test_pipeline.py`, `tests/test_golden.py`, `TESTING.md` routing table, plus
the live issue #176 body via `gh issue view 176` (verbatim match to cached
`tests/fixtures/t2/I2.md`) as the specification. Gaps found & folded in: none — issue text was
accurate against current source; folded in explicit edge-case reasoning (unknown region, zero
amount, negative-amount guard ordering) and a golden-artifact byte-diff check as an extra
verification step beyond just trusting `test_golden.py`.

🔍 CP1 GATE — <pending>
