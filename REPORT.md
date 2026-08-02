# REPORT — Issue #8: Split the fee calculation into its two components

Ruling count (RULINGS.md): 6.

## CP1 gate outcome

Verdict: ADVISORY (implement as planned). Two findings, both corrected in `PLAN.md` before
implementation:

1. `PLAN.md:20` overstated existing coverage — only
   `test_apply_fees_charges_the_regional_handling_rate` reaches `fee_for()`;
   `test_apply_fees_rejects_a_negative_gross_amount` raises `ValueError` in `apply_fees()`
   before `fee_for()` is called. Corrected the sentence, no design change.
2. `PLAN.md:74` misdescribed `.get(..., 0)` as covering "unknown/missing region." Corrected: an
   *unknown* region value uses the `.get` default; a *missing* `region` key raises `KeyError`
   from `record["region"]` before `.get` ever runs. Per coordinator adjudication, this KeyError
   is preserved exactly — no guard was added around the key lookup.

## Re-measurement of the issue itself

The issue (#8) was correct as written; nothing in its body was corrected. `fee_for()` had exactly
one caller (`apply_fees()`), no other file referenced `fee_for`/`FLAT_FEE`/`HANDLING_BP` by name.

## Implementation

`src/normalise.py`: extracted `_flat_component(record)` (returns `FLAT_FEE`, never touches
`record["region"]`) and `_handling_component(record)` (verbatim
`record["amount"] * HANDLING_BP.get(record["region"], 0) // 10000`, same multiply-then-floor-div
order as the original single expression). `fee_for()` now returns their sum. No public names
changed; `apply_fees()` untouched.

`tests/test_pipeline.py`: added `test_flat_and_handling_components_sum_to_fee_for` (pins the
split and the non-exact-division operator order using `amount=999, region="EU"` -> `149`) and
`test_fee_for_raises_on_a_record_missing_region` (pins the `KeyError` on a record without a
`region` key).

## Mutation testing (authored before declaring tests done)

Both mutations were applied by editing `src/normalise.py`, run against the single targeted test,
confirmed the failure, then reverted before the next mutation, and verified via `git diff` /
inspection afterward that the file matched the pre-mutation content exactly.

- mutation 1 @ `src/normalise.py:18` (`_handling_component`, `amount * bp // 10000` reordered to
  `bp // 10000 * amount`) -> killed by `test_flat_and_handling_components_sum_to_fee_for`
  (assertion `_handling_component(record) == 999 * HANDLING_BP["EU"] // 10000 == 149` failed,
  observed `0 == 149`).
- mutation 2 @ `src/normalise.py:18` (`HANDLING_BP.get(record["region"], 0)` changed to
  `HANDLING_BP.get(record.get("region"), 0)`, silently swallowing a missing `region` key) ->
  killed by `test_fee_for_raises_on_a_record_missing_region` (`pytest.raises(KeyError)` block
  failed to raise).

No survivors: 2 mutations authored, 2 killed, listed individually above per the reporting
contract (aggregate "N mutations, 0 survivors" phrasing avoided).

## Gates

- `python -m compileall -q src` -> pass (exit 0).
- `python -m ruff check .` -> pass (exit 0, "All checks passed!"). A harmless
  `warning: Encountered error: Access is denied. (os error 5)` appeared before the pass line -
  this is ruff's file-walk hitting a Windows-locked `pytest-of-emile` temp directory unrelated to
  the change, not a lint finding; it did not affect the exit code or the checked files.
- `python -m pytest -q` -> pass, **33 passed** (baseline 31 + 2 new tests added by this change; 0
  skipped, 0 collection errors, 0 change to the flaky test's status since
  `FACTORY_TESTBED_FLAKE` was not set).

## Golden artifact

`git diff -- artifacts/report.golden.txt` is empty - byte-for-byte unchanged, confirmed after the
full change and before commit, satisfying the issue's explicit constraint. `tools/write_golden`
was not run (nothing to regenerate).

## Null-control check (per coordinator's note)

This item is the run's null control, expected to be a genuine no-behaviour-change refactor. That
expectation held under execution: the golden artifact is untouched, `fee_for()`'s new body is
algebraically identical to its old body for every input (including the `KeyError` path on a
missing `region`, preserved rather than papered over), and the only observable change to the
codebase's tests is two new passing tests. No contradicting evidence found.

## TESTING.md routing

Touched the "fees" row (`src/normalise.py` -> `tests/test_pipeline.py`); ran that suite plus the
full suite for depth-A confidence. No other row touched.

## Files changed

- `src/normalise.py`
- `tests/test_pipeline.py`
- `PLAN.md` (corrected per CP1 gate findings, kept as audit trail)

## Uncovered by gates

None among changed files - both `src/normalise.py` and `tests/test_pipeline.py` are exercised
directly by `python -m pytest -q`, and both are Python source covered by `compileall`/`ruff`.

## Two places I would attack next if reviewing this myself

1. `_flat_component(record)` takes an unused `record` parameter purely for signature symmetry
   with `_handling_component`. A reviewer could reasonably call this scope creep beyond "extract
   two helpers" - ruff did not flag the unused argument (it's a private function whose parameter
   is part of its declared signature, not dead code), but it's worth a second look at whether an
   argument-less `_flat_component()` would have been the more minimal choice.
2. The new `test_fee_for_raises_on_a_record_missing_region` test locks in `KeyError` as
   contractual behavior for a missing `region` field, but this may be under-specified upstream -
   if `check_record()` in `src/validate.py` already guarantees `region` is always present on
   validated records reaching `fee_for()`, this test pins behavior on an input shape that may
   never occur in the real pipeline. Worth checking whether that guarantee exists.
