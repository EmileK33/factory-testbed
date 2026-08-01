# PLAN — Add `summarise_records` (issue #2)

## What I verified before planning

- `src/records.py` exists and exposes `load_records(path=None)`, returning `list[dict]`.
  Verified by reading the file.
- `src/validate.py` exposes `check_record(record: object) -> dict | None`, which returns `None`
  for a record failing any of: not a dict, missing/empty one of
  `VALIDATED_FIELDS = ("id", "name", "amount", "currency", "region")`, region not in
  `REGION_CODES`, currency not in `CURRENCY_CODES`, amount not a non-bool int, or amount < 0.
  There is no `validate_record` anywhere in the repo (`grep -rn validate_record` → no hits).
- `tests/test_records.py` has 6 tests (verified with
  `python -m pytest tests/test_records.py --collect-only -q`), not 14 as the issue originally
  claimed. Issue corrected (see below).
- `data/records.json` has 8 rows. One (`Fennel Labs`) has no `id` key at all — the existing
  fixture I will reuse for the "missing id" edge case. One (`Garnet Rail`) has an unknown
  currency (`GBP`). One (`Halcyon Air`) has a non-numeric `amount` (`"n/a"`). These give me three
  independent drop reasons already present in the live feed, plus the missing-id row, without
  inventing new fixture data.
- `src/summarise.py` already defines an unrelated `summarise(records)` (different name, different
  return shape: `{"total", "accepted", "rejected": [ids]}`), used by `tests/test_pipeline.py`.
  Confirmed via `CLAUDE.md`/`TESTING.md` layout tables and by reading `src/summarise.py`. I will
  not touch it — `summarise_records` is a new, differently-shaped function that belongs on
  `src/records.py` per the issue's explicit instruction.
- Baseline: `python -m pytest -q` → `31 passed`. `python -m compileall -q src` and
  `python -m ruff check .` both currently pass (exit 0).

## What I will change

### `src/records.py`
Add one new function, appended after `load_records`:

```python
def summarise_records(records: list[dict]) -> dict:
    """Return counts of *records*: total seen, valid (passes check_record), dropped."""
```

- Import `check_record` from `src.validate` at module top (`from src.validate import check_record`).
- Implementation: iterate `records`, call `check_record(record)` for each; count `None` results as
  dropped, everything else as valid; `total = len(records)`; return
  `{"total": total, "valid": valid_count, "dropped": dropped_count}`.
- No mutation of input; no reliance on `record["id"]` being present, since `check_record` already
  handles a missing/empty `id` by returning `None` — I do not need to special-case it, but I will
  add a dedicated test naming that behaviour explicitly per the issue's requirement ("records with
  a missing id must be counted as dropped").
- I will NOT modify `load_records`, `DATA_PATH`, or any existing symbol in this file.

### `tests/test_records.py`
Add tests only — no edits to existing test bodies or assertions:

1. `test_summarise_records_counts_a_clean_feed` — build a small in-memory list of all-valid
   records (reusing the `CLEAN`-style shape from `tests/test_validate.py`, defined locally since
   `tests/test_records.py` does not currently import that fixture), call `summarise_records`,
   assert `total == valid == len(list)` and `dropped == 0`.
   - What breaks if the code is wrong: an off-by-one in the accept branch, or accidentally
     counting a valid record as dropped, flips this to fail immediately since it pins the
     "everything passes" boundary.

2. `test_summarise_records_counts_a_mixed_feed_against_the_live_data` — call
   `summarise_records(load_records())` against the real `data/records.json` and assert the exact
   `total`/`valid`/`dropped` numbers (computed independently in the test via
   `sum(1 for r in load_records() if check_record(r) is not None)` rather than hard-coded, so the
   test doesn't silently drift if the fixture data changes, but still cross-checks
   `total == len(records)` and `valid + dropped == total`).
   - What breaks if wrong: any arithmetic mistake in how `valid`/`dropped` are derived from
     `check_record`'s per-record `None`/dict result.

3. `test_summarise_records_drops_a_record_with_no_id` — pass a single-element list containing a
   record with every `VALIDATED_FIELDS` key except `id` (mirrors
   `tests/test_validate.py::test_check_record_drops_a_record_with_no_id`'s fixture shape); assert
   `summarise_records([...]) == {"total": 1, "valid": 0, "dropped": 1}`.
   - What breaks if wrong: this is the issue's explicit acceptance criterion — if a future edit to
     `summarise_records` special-cased `id` incorrectly (e.g. checked `"id" in record` instead of
     delegating to `check_record`, and mishandled an empty string `id`), this test catches it
     directly, independent of the rest of the validation contract.

4. `test_summarise_records_handles_an_empty_list` — `summarise_records([])` ==
   `{"total": 0, "valid": 0, "dropped": 0}`.
   - Edge case: the empty-collection boundary. What breaks if wrong: a division, an
     unguarded `records[0]`, or an off-by-one in a manual counter would raise or return wrong
     shape on the empty input; this pins the function to return the same three keys with all
     zeros rather than raising or omitting keys.

5. `test_summarise_records_counts_are_consistent_with_totals` — property-style check: for a
   constructed list mixing several valid and several invalid records (explicit literal list, not
   randomised), assert `result["total"] == result["valid"] + result["dropped"]` and
   `result["total"] == len(input_list)`.
   - What breaks if wrong: a record that is neither counted as valid nor dropped (e.g. an
     exception path swallowed silently, or a record type `check_record` doesn't recognise) would
     violate this invariant even if the individual valid/dropped numbers look plausible in
     isolation.

No new test file is needed — these fit `tests/test_records.py`'s existing scope (loading module),
and `TESTING.md`'s routing table already points `src/records.py` → `tests/test_records.py`. I will
not add a row to `TESTING.md` since the existing row already covers this file; if the reviewer
wants the row's wording ("reads `data/records.json`") extended to mention `summarise_records`,
that's a one-line addition I'd take as review feedback, not something I'm doing unprompted this
turn (no code is being written this turn regardless).

## Edge cases and error paths covered

- Empty list input → `{"total": 0, "valid": 0, "dropped": 0}` (test 4).
- Missing `id` field specifically, since the issue calls it out by name (test 3).
- Records that are invalid for other reasons already present in the live feed (bad currency,
  non-numeric amount) are exercised indirectly by test 2 against the real feed, and directly by
  the mixed literal list in test 5.
- `summarise_records` does not raise on any input `check_record` already tolerates (non-dict rows,
  since `check_record` guards with `isinstance(record, dict)` and returns `None` rather than
  raising) — I will add no new exception path; `summarise_records` itself never raises for any
  list of arbitrary objects, because it only ever calls `check_record(record)` and branches on its
  return value, and `check_record` is documented/tested to accept `object` and never raise.
- `total`/`valid`/`dropped` are always non-negative ints and always sum consistently — pinned by
  test 5's invariant rather than assumed.

## What I will NOT touch (scope boundary)

- `src/validate.py` — read-only; `summarise_records` calls `check_record` but the file is not
  edited.
- `src/report.py` and `artifacts/report.golden.txt` — untouched; `render_report` does not call
  `summarise_records`, and I am not wiring it in.
- `src/summarise.py` and its existing `summarise()` — untouched; different function, different
  file, out of scope per the issue and per the scope boundary given to me.
- `tests/test_report.py`, `tests/test_golden.py`, `tests/test_validate.py`, `tests/test_parse.py`,
  `tests/test_pipeline.py`, `tests/test_flaky.py` — no assertions in any existing test are
  changed. I add new test functions to `tests/test_records.py` only.
- `TESTING.md`, `CLAUDE.md`, `README.md`, `ruff.toml`, `pytest.ini`, `tools/write_golden.py`,
  `data/records.json` — untouched.
- No new module/file is created; `summarise_records` lives in the existing `src/records.py` as the
  issue specifies.

## Gates I will run once code is written (not this turn)

```
python -m compileall -q src
python -m ruff check .
python -m pytest -q
```
Expect 31 + 5 = 36 passed, with no change to the previously-passing 31.
