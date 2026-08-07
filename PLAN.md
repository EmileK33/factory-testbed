# PLAN — Issue #150: T2 negctl-parallelism I1 (sequential control)

## Re-measurement result

Issue text (`gh issue view 150`, matches cached `ITEM-ISSUE.md` and
`tests/fixtures/t2/I1.md` verbatim) is **accurate against current source** —
no `gh issue edit` correction needed. Verified:

- `src/report.py::REPORTED_FIELDS = ("id", "name", "region", "amount", "currency")`
  does drive `_table()`'s columns (widths computed once per `_table()` call).
- `src/validate.py::check_record()` already calls `parse_tags()` and always
  sets `"tags"` on the returned dict (line 62), so every accepted row already
  carries a normalised `list[str]`.
- The report currently never reads that key — `tags` is absent from
  `REPORTED_FIELDS` and from every rendered line.
- `artifacts/report.golden.txt` / `tests/test_golden.py` do byte-for-byte
  comparison, so the artifact needs regenerating via `python -m tools.write_golden`
  (per `CLAUDE.md`), not hand-editing.

Baseline gates on the untouched tree: `compileall` clean, `ruff check .` →
"All checks passed!", `pytest -q` → 31 passed (4 of them in `test_report.py`).

## Gaps found against Complete/Robust/Fault-tolerant (folded into the plan)

1. **Empty-tags cell would misrender.** `_cell()`'s `_missing()` check is
   `value is None or value == ""`. A record with no `tags` column normalises
   to `[]` (via `parse_tags(record.get("tags", ""))` → `parse_tags("")` →
   `[]`), and `[] == ""` is `False`, so today's `_missing` would treat an
   empty tag list as *present* and `_cell` would render the literal
   `str([])` → `"[]"` instead of the report's blank convention `"-"`. Fix:
   extend `_missing()` to also treat `[]` as missing (safe — its only other
   caller, the "Unlabelled records" line, never passes a list).
2. **List values need join formatting, not `str()`.** A non-empty tags list
   passed through the existing `str(value)` path renders as
   `"['eu', 'high', 'priority', 'settled']"`, not a report-appropriate cell.
   Fix: `_cell()` joins `list` values with `", "`.
3. **"All N reported fields are checked by the validation rules" becomes
   false once `tags` is added.** `VALIDATED_FIELDS` (id, name, amount,
   currency, region — 5) does not and should not include `tags`:
   `check_record()` treats tags as optional/normalised, never rejects on it.
   Today `REPORTED_FIELDS == VALIDATED_FIELDS` in content (5 fields each), so
   the sentence is true by coincidence. Appending `tags` makes `REPORTED_FIELDS`
   6 items while only 5 are actually validated — the literal sentence
   "All 6 reported fields are checked by the validation rules" would then be
   false. Fix: compute the intersection generically (`[f for f in
   REPORTED_FIELDS if f in validate.VALIDATED_FIELDS]`) and change the wording
   to "`{checked} of {total} reported fields are checked by the validation
   rules.`" — stays truthful now and if a future item (I9) adds more columns.
4. **No test pins the empty-tags case.** Every row currently in
   `data/records.json` happens to carry non-empty tags, so a naive test suite
   would never exercise the blank-cell path. Add a test that calls
   `render_report(records=[...])` with an explicit record missing the `tags`
   key, asserting the row renders `"-"` in that column.

## Implementation

**`src/report.py`**
- `REPORTED_FIELDS = ("id", "name", "region", "amount", "currency", "tags")`
  (append — minimal diff, matches the notes' "extra column" framing).
- `_missing()`: `return value is None or value == "" or value == []`.
- `_cell()`: after the missing check, `if isinstance(value, list): return
  ", ".join(str(item) for item in value)`; else `str(value)` as today.
- Replace the "All N reported fields…" line with the truthful, generically
  computed "X of Y reported fields are checked by the validation rules."
  wording described in gap 3.

**Out of scope (flagged, not fixed):** `src/parse.py::parse_tags()`'s
docstring claims a comma inside quotes stays one tag, but the actual splitter
(`_TAG_SEPARATOR = re.compile(r",\s*")`) splits before stripping quotes, so
R-1001's `"high,priority"` becomes two tags `high`, `priority` rather than
one. This is a pre-existing defect, unrelated to wiring `tags` into
`REPORTED_FIELDS`, and the issue's notes scope the change to `report.py`
only. I will render what `parse_tags` actually produces (matching current,
if arguably wrong, behavior) and report this as an escalation rather than
fix `src/parse.py` — fixing it would also change I3's future by-tag counts
in ways this issue doesn't ask for.

**Tests (`tests/test_report.py`)**
- `test_report_shows_tags_for_accepted_records` — for every accepted row,
  assert `", ".join(tags)` appears in the rendered text.
- `test_report_renders_a_dash_for_a_record_with_no_tags` — call
  `render_report(records=[...])` with one well-formed record that omits the
  `tags` key; assert its row's tags cell is `-`.
- `test_report_states_how_many_reported_fields_are_validated` — compute the
  expected "X of Y" string from `REPORTED_FIELDS`/`validate.VALIDATED_FIELDS`
  the same way `report.py` will, assert it's present (not hardcoded numbers,
  so it doesn't silently stop testing the real logic if the field sets change
  later).

**Golden artifact**
- Regenerate via `python -m tools.write_golden` after the code change; diff
  it by eye before committing (new `tags` column added at the right edge,
  existing columns/values unchanged, new "X of Y reported fields…" line).

**Untouched on purpose:** `TESTING.md`, `CLAUDE.md`'s artifact description —
per `tests/fixtures/t2/I6.md`, doc catch-up is a separate item that
deliberately waits on *every* report-shape item, not this one alone.
`src/parse.py`, `src/summarise.py`, `data/records.json` — not implicated by
this issue's notes.

## Gates to run after implementation

```
python -m compileall -q src
python -m ruff check .
python -m pytest -q
```

---

🔍 CP1 — re-read: `src/report.py` (all of it), `src/validate.py::check_record`/`VALIDATED_FIELDS`,
`src/parse.py::parse_tags`, `src/records.py`, `data/records.json`, `artifacts/report.golden.txt`,
`tools/write_golden.py`, `tests/test_report.py`, `tests/test_golden.py`, `tests/test_validate.py`,
`tests/test_parse.py`, `tests/test_pipeline.py`, `tests/test_counts.py`, `TESTING.md`, `CLAUDE.md`
(report/golden sections), and the specification: `gh issue view 150` plus its cached copies
`ITEM-ISSUE.md` and `tests/fixtures/t2/I1.md` (identical text), read in full, plus sibling fixtures
`tests/fixtures/t2/{I2,I3,I5,I6,I9}.md` for forward-looking scope boundaries (I3 depends on this
column existing; I6 owns doc catch-up and waits on all report items; I9 owns the rejection footer).
Gaps found & folded in: (1) empty-tags cell would render `"[]"` instead of `"-"` — extended
`_missing()`; (2) non-empty tags list would render as a Python list repr instead of a joined string
— added list handling to `_cell()`; (3) "All N reported fields are checked by the validation rules"
becomes false once an unvalidated field (`tags`) is reported — reworded to a generically computed
"X of Y" count; (4) no existing data row has empty tags, so the blank-cell path needed an explicit
test with a synthetic record.

🔍 CP1 GATE — pending.
