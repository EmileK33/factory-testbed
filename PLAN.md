# PLAN — Issue #151: T2 negctl-parallelism I2 (sequential control)

## Re-measurement against actual current source

(Note: this worktree's `PLAN.md` previously contained a stale plan for a
different item, #150/I1 — the tags-column work. That work is already merged
to `main` as `#152` and is irrelevant to this item; this file replaces it.)

Read `src/normalise.py` as it exists on `negctl-seq-151` (which already
includes main's merged `#152`). `fee_for()` today:

```python
def fee_for(record: dict) -> int:
    """Return the total fee charged against *record*."""
    return FLAT_FEE + record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000
```

`*` and `//` are equal precedence, left-to-right, so this evaluates as
`FLAT_FEE + ((amount * HANDLING_BP.get(region, 0)) // 10000)` — a flat
component plus a handling component, exactly as the issue describes. The
issue's file path, function name, and both proposed helper names
(`_flat_component`, `_handling_component`) match the real code. **No
correction needed via `gh issue edit`** — verified against `gh issue view 151`
live output, which matches the cached `ITEM-ISSUE.md` and
`tests/fixtures/t2/I2.md` verbatim.

Confirmed independent of `#152` (tags column, already merged to `main` and
present in this worktree): `#152` touched only `src/report.py`,
`tests/test_report.py`, and regenerated `artifacts/report.golden.txt` to add
a `tags` column. It did not touch `src/normalise.py`. `report.py` does call
`apply_fees()` (→ `fee_for()`) to render the "Net after fees" section, so the
golden file's byte-for-byte check *does* transitively cover `fee_for()` — that
is exactly why the issue's stated constraints ("`fee_for()` must return an
identical value for every input" and "golden file byte-for-byte unchanged")
are real, checked acceptance criteria here, not boilerplate.

Existing coverage found:
- `tests/test_pipeline.py` (per `TESTING.md`'s routing table, this is the row
  for `src/normalise.py`, "coupled to no data file") —
  `test_apply_fees_rejects_a_negative_gross_amount`,
  `test_apply_fees_charges_the_regional_handling_rate` (exercises `fee_for`
  indirectly via `apply_fees`, EU region: `25 + 150` fee math).
- `tests/test_golden.py` — byte-for-byte check of
  `artifacts/report.golden.txt` against `render_report()`, which transitively
  exercises `fee_for()` for every accepted record in the live feed.

No labels are set on `#151`, and none on sibling issues `#150`/`#152` either
— no labeling convention to correct.

**Correction made to the issue: none.** The issue is accurate as written.

## Gaps found against Complete/Robust/Fault-tolerant (folded into the plan)

1. **Complete:** the two new helpers need their own direct unit coverage, not
   just indirect coverage through `fee_for`/`apply_fees`/the golden file —
   otherwise a bug that cancels between the two components (e.g. swapped
   terms) could still pass every existing assertion. Folding in two new tests
   that check each helper's return value independently (see Tests below).
2. **Robust:** `_flat_component` has no natural use for `record`, but giving
   it the same `(record: dict) -> int` signature as `_handling_component`
   keeps both callable uniformly and matches the issue's "two components"
   framing without introducing an asymmetric private API. This is a judgment
   call, not a defect — noting it here rather than treating it as a gap to
   silently resolve.
3. **Fault-tolerant:** no new failure mode is introduced — both helpers only
   perform the same arithmetic/dict lookups `fee_for()` already performed
   inline, on the same inputs, so any input that previously raised (e.g.
   missing `"amount"`/`"region"` key) still raises at the same point, and no
   input that previously succeeded can newly raise.

## Implementation

In `src/normalise.py`, replace the single-expression `fee_for()` with:

```python
def _flat_component(record: dict) -> int:
    return FLAT_FEE


def _handling_component(record: dict) -> int:
    return record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000


def fee_for(record: dict) -> int:
    """Return the total fee charged against *record*."""
    return _flat_component(record) + _handling_component(record)
```

`FLAT_FEE` and `HANDLING_BP` module constants are untouched (no public-name
changes, per the issue's constraint). `apply_fees()` is untouched — it only
calls `fee_for()`.

## Tests

Add to `tests/test_pipeline.py` (same file per `TESTING.md`'s routing row for
fees — no reason to split it further for an internal refactor):

- `test_flat_component_is_constant_regardless_of_region_or_amount` — asserts
  `_flat_component()` returns `FLAT_FEE` across differing amount/region
  combinations (including a region absent from `HANDLING_BP`).
- `test_handling_component_applies_the_regional_basis_points` — asserts
  `_handling_component()` alone equals `amount * HANDLING_BP[region] //
  10000` for an EU record (non-zero bp) and an APAC record (zero bp), and
  that `_flat_component(r) + _handling_component(r) == fee_for(r)` for both.

Existing `tests/test_pipeline.py` tests are left unmodified — `fee_for()`'s
external behavior is unchanged by contract, so they must keep passing as-is.

No golden-file regeneration: `fee_for()`'s output is unchanged by
construction, and `tests/test_golden.py` is the byte-for-byte proof of that.
I will positively confirm `git diff --stat artifacts/report.golden.txt` shows
no changes, not just rely on the test passing.

## Gates (after implementation)

```
python -m compileall -q src
python -m ruff check .
python -m pytest -q
```

## Two places I'd attack next (adversarial)

1. Ruff's unused-argument behavior on `_flat_component(record)` — `record` is
   unused inside that function. Will check `ruff check .` output; if it flags
   this (repo's ruff config may or may not enable that rule — no other
   unused-parameter pattern exists elsewhere in `src/` to compare against), I
   will resolve it in-scope rather than suppress, by whichever means keeps the
   two helpers symmetric.
2. Re-diff `artifacts/report.golden.txt` after the change (`git diff --stat`)
   to positively confirm zero bytes changed, not just that
   `tests/test_golden.py` passes — belt-and-suspenders on the issue's
   "byte-for-byte unchanged" constraint, since a passing test and an
   unexamined diff would look identical if the test itself had a latent gap.

---

🔍 CP1 — re-read: `src/normalise.py` (all of it, current worktree state including
merged `#152`), `src/report.py` (to confirm `apply_fees`/`fee_for` call path and
independence from the tags-column change), `tests/test_pipeline.py`,
`tests/test_golden.py`, `tests/fixtures/t2/I2.md`, `TESTING.md`'s routing table,
and the specification: `gh issue view 151` (live) plus cached `ITEM-ISSUE.md` and
`tests/fixtures/t2/I2.md`, all read in full and cross-checked against each other
(identical text, no drift). Also checked `#150`/`#152` (predecessor sequential
item, merged) to confirm no overlap with `src/normalise.py`.
Gaps found & folded in: (1) new helpers had no direct unit test path distinct
from existing indirect coverage through `fee_for`/`apply_fees`/the golden file —
added two direct tests; (2) no other gap — this is a mechanical, contract-
preserving extraction with an existing regression net (`test_apply_fees_*`,
`test_golden.py`) that already pins `fee_for()`'s exact output.

🔍 CP1 GATE — pending.
