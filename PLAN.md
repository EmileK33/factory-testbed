# PLAN — Issue #79: Correct two malformed records in the settlement feed

## Re-measurement summary (Step 1)

Checked every factual claim in #79 against the real tree:

- `data/records.json` R-1007 (Garnet Rail): confirmed `"currency": "GBP"`, `"amount": 640`,
  `"region": "EU"`. `GBP` is not in `src/validate.py`'s `CURRENCY_CODES = ("EUR", "USD", "JPY")`,
  so `check_record()` rejects it on the currency check. Confirmed via a direct run of
  `check_record()` over `load_records()`: `R-1007 Garnet Rail -> REJECT`.
- `data/records.json` R-1008 (Halcyon Air): confirmed `"amount": "n/a"` (a string), region `NA`,
  currency `USD`. `_is_whole_number()` requires `isinstance(value, int)` and rejects the string,
  so `check_record()` rejects it. Confirmed: `R-1008 Halcyon Air -> REJECT`.
- Fennel Labs row: confirmed it has no `"id"` key at all. `VALIDATED_FIELDS` includes `"id"`, and
  `_missing()` treats a missing key as missing, so it is rejected today and would stay rejected
  regardless of this change. Confirmed: `None Fennel Labs -> REJECT`.
- Simulated the prescribed corrections in memory (currency `GBP`→`EUR` for R-1007, amount
  `"n/a"`→`720` for R-1008) and ran them through the real `check_record()`: both now return a
  normalised record (ACCEPT). `(EU, EUR)` and `(NA, USD)` are both in `ALLOWED_PAIRS`, both
  amounts are positive plain ints, so both clear every check in `src/validate.py`.
- Full-repo `grep` for `R-1007`, `R-1008`, `GBP`, `n/a`, `640`, `720` turned up nothing outside
  `data/records.json`, `tests/fixtures/t2/I7.md` (the issue's own source fixture, identical text),
  and `tests/test_pipeline.py:62`, which pins the *current* rejection as part of
  `test_summarise_counts_the_feed_it_was_given` (see below). `tests/test_validate.py:43`'s GBP
  case uses a synthetic `CLEAN` record unrelated to R-1007's data, so it is unaffected.

**Verdict: every factual claim in issue #79 checks out against the real tree.** Nothing to
correct — the issue body will not be edited. (Per the mandatory sequence, this is my own
re-measurement; a reviewer should re-check the commands above rather than take the verdict on
trust.)

## What changes

1. **`data/records.json`** (the only source file, per the issue's own scope note):
   - R-1007: `"currency": "GBP"` → `"currency": "EUR"`. Leave `"amount": 640` and everything else
     on that row untouched — the issue does not claim the amount is wrong, and it already
     validates once the currency is fixed.
   - R-1008: `"amount": "n/a"` → `"amount": 720` (a JSON number, not a string). Leave currency/
     region untouched.
   - Fennel Labs row: no change. No `id` is invented.

2. **Three tests move as a result of the data fix.** (Round 1 gate finding: my first draft found
   only one and asserted "no other tests move" — a claim about everything I hadn't checked. Naming
   all three here instead.)

   - `tests/test_pipeline.py::test_summarise_counts_the_feed_it_was_given` — **needs an edit.**
     Hardcodes `counts["accepted"] == 5` and
     `counts["rejected"] == ["<unlabelled>", "R-1007", "R-1008"]` against the real feed. After the
     data fix these become `7` and `["<unlabelled>"]`. This is a test-data coupling issue, not a
     change to `src/validate.py` itself — the validator, loader, and rendering code stay
     untouched, exactly as the issue asks. I will first run the suite with only the data fix
     applied to confirm this test fails (breaking it), then update its two literal assertions to
     match, confirming it passes.
   - `tests/test_golden.py::test_report_matches_the_committed_golden_artifact` — **self-correcting,
     but only once I regenerate the artifact.** It compares `render_report()`'s live output
     against the committed `artifacts/report.golden.txt` byte-for-byte. It has no literal of its
     own to edit; it will fail the moment the data changes (the live render no longer matches the
     stale committed file) and pass again once I run `python -m tools.write_golden`, which is
     already step 3 below. No source edit needed in this test itself.
   - `tests/test_report.py::test_report_lists_every_accepted_record` — **self-correcting, no edit
     needed.** It computes its own expected set at test time
     (`[row for row in (check_record(r) for r in load_records()) if row]`) rather than hardcoding
     ids, so once R-1007 and R-1008 become acceptable they are simply added to both sides of the
     comparison and the assertion (`row["id"] in text`) continues to hold. Its accepted-record-id
     set does change composition (5 ids → 7), but nothing about the test's source needs editing.

   I re-checked every other test file for the same class of coupling (`grep` above plus a full
   read of `tests/test_validate.py`, `tests/test_records.py`, `tests/test_report.py`,
   `tests/test_golden.py`): `test_validate.py`'s GBP/id/currency cases all use the synthetic
   `CLEAN` fixture, not the real feed, and are unaffected. `tests/test_report.py`'s other
   assertions (`test_report_reports_the_counts_it_read`, `test_report_names_the_unlabelled_record`,
   `test_report_shows_each_accepted_records_tags`, `test_report_states_how_many_reported_fields_are_validated`,
   etc.) are either dynamically derived or pinned to rows/fields (R-1001..R-1005, Fennel Labs, the
   `REPORTED_FIELDS`/`VALIDATED_FIELDS` counts) that this change does not touch, so they are
   unaffected. `tests/test_records.py` and `tests/test_golden.py`'s
   `test_the_golden_artifact_is_committed` check file existence/shape, not R-1007/R-1008's values,
   and are unaffected. So exactly three tests move (one needing a source edit, two self-correcting
   as described above); everything else in the suite is unaffected by this change.

3. **`artifacts/report.golden.txt`**: regenerate with `python -m tools.write_golden` after the
   data fix, per `CLAUDE.md`. I previewed the resulting report by rendering with the corrected
   records in memory (without touching the file, via a throwaway script — the committed file was
   not modified during planning). **Concrete expected values, recorded here so a wrong
   regeneration is visible rather than silently absorbed:**

   - `Records read: 8` (unchanged)
   - `Records accepted: 5` → `Records accepted: 7`
   - `Records rejected: 3` → `Records rejected: 1`
   - `Unlabelled records: Fennel Labs` (unchanged — still the sole rejection)
   - `Total (USD): 4595.66` → `Total (USD): 6019.66`
   - New rows appear for `R-1007` (`EU  640  EUR  eu, rail`, net `519` after fees) and `R-1008`
     (`NA  720  USD  na, air`, net `659` after fees) in both the main table and the "Net after
     fees" section.

   I will not hand-edit the artifact; I will let `write_golden` produce it, then read the
   regenerated file and check every value above against it. If any value differs from what's
   listed here, I will stop and report the discrepancy rather than accept it.

## Files touched

- `data/records.json` (data correction)
- `tests/test_pipeline.py` (update the two literal assertions coupled to the corrected data)
- `artifacts/report.golden.txt` (regenerated via `python -m tools.write_golden`, not hand-edited)

No changes to `src/validate.py`, `src/records.py`, `src/report.py`, or any other rendering/loader
code — consistent with the issue's explicit scope note.

## Test plan

1. Confirm current baseline is green: `python -m pytest -q` (currently: 41 passed, 1 xfailed;
   the xfail is the known, separately-tracked `parse.py` quoted-tag defect and is out of scope).
2. Apply only the `data/records.json` edit. Re-run `python -m pytest -q` and confirm exactly
   `tests/test_pipeline.py::test_summarise_counts_the_feed_it_was_given` and
   `tests/test_golden.py::test_report_matches_the_committed_golden_artifact` fail (the latter
   because the golden artifact is now stale) — this is the "break it and confirm it fails first"
   check for the test I'm about to edit, and confirms the golden-mismatch fires as expected.
3. Update the two literal values in `test_summarise_counts_the_feed_it_was_given`. Re-run
   `python -m pytest -q tests/test_pipeline.py` and confirm it passes.
4. Run `python -m tools.write_golden` to regenerate the artifact. Read the regenerated
   `artifacts/report.golden.txt` and check it against the concrete values recorded above
   (accepted 5→7, rejected 3→1, Total (USD) 4595.66→6019.66, the two new rows) before trusting
   it; stop and report if any value differs. Then re-run
   `python -m pytest -q tests/test_golden.py tests/test_report.py` and confirm both pass.
5. Full gate pass: `python -m compileall -q src`, `python -m ruff check .`,
   `python -m pytest -q` — expect the same 41 passed, 1 xfailed (same xfail, unrelated to this
   change) with no new failures.
6. Explicitly re-verify the Fennel Labs / no-id row is still rejected after the fix
   (`tests/test_records.py::test_load_records_keeps_the_row_with_no_id` and
   `tests/test_validate.py::test_check_record_drops_a_record_with_no_id` already cover this via
   the synthetic case; I will additionally re-run the same manual `check_record()`-over-
   `load_records()` sweep used in Step 1 to confirm Fennel Labs is still the *only* remaining
   rejection and that no `id` was invented for it).
7. Diff the freshly-generated `artifacts/report.golden.txt` by eye against the in-memory preview
   already captured during planning, to catch anything write_golden produced that I didn't expect.

## Edge cases considered

- **Fennel Labs must stay rejected.** Explicitly not touched; verified rejected before and after
  via the manual sweep and existing tests. This is the "record that must stay rejected" the
  mandatory sequence calls out — it will be pinned by the (unedited) existing tests plus my
  manual re-check in step 6 above, not silently swept up by a broad `git add`.
- **R-1007's amount (640) is not touched** — issue only flags the currency field for R-1007; I
  verified 640 is already a valid positive int so no further edit is needed there.
- **JSON type correctness for R-1008**: the fix must be the JSON number `720`, not the string
  `"720"` — `_is_whole_number()` requires `isinstance(value, int)`, so a quoted string would
  still fail validation. I will write it unquoted and confirm via `check_record()`.
- **Golden artifact newline/encoding**: `write_golden` pins `newline="\n"` and `.gitattributes`
  pins `eol=lf` repo-wide, so no platform-specific line-ending drift is expected on this Windows
  checkout; `test_golden.py` compares bytes, which will catch it if I'm wrong.
- **No invented `id` for Fennel Labs, and no touching `src/validate.py`, `src/records.py`, or
  `src/report.py`** — explicitly out of scope per the issue, confirmed unnecessary by the Step 1
  re-measurement (both target rows validate correctly under the existing, unmodified contract
  once their data is corrected).

## Risks

- Low risk overall — this is a two-field data edit plus a golden regeneration and one coupled
  test update. The main risk is under-scoping the test sweep (missing a test hardcoded against
  the old rejected state); mitigated by the full-repo grep above and the explicit read of every
  test file that touches `load_records()`/`check_record()`/`summarise()`.
- Secondary risk: hand-drifting the golden artifact instead of using `write_golden`, which would
  violate the repo's own byte-for-byte contract. Mitigated by using the tool exclusively and
  verifying via `test_golden.py`.
