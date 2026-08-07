# PLAN — Issue #175: Show each record's tags in the settlement report

## Re-measured facts

- `src/report.py`: `REPORTED_FIELDS = ("id", "name", "region", "amount", "currency")`
  drives both the header/row rendering (`_table`) and the summary line
  `f"All {len(REPORTED_FIELDS)} reported fields are checked by the validation rules."`
- `src/validate.py`: `check_record()` already returns `"tags": parse_tags(...)` — a
  `list[str]`, normalised by `src/parse.py:parse_tags`. `VALIDATED_FIELDS = ("id",
  "name", "amount", "currency", "region")` does **not** include `tags` — tags is
  never validated, only normalised.
- `_cell(row, field)` currently does `str(value)` for any non-missing value.
  Once `tags` (a `list[str]`) is added to `REPORTED_FIELDS`, this would render
  Python list repr, e.g. `['eu', 'high,priority', 'settled']`, on every row —
  not usable output for Operations, who is the stated audience.
- `_missing(value)` (report.py's copy) is `value is None or value == ""`. An
  empty list (`[]`) — which `parse_tags` returns for a blank/absent `tags`
  column — is not caught by this, so an unpatched cell path would print `"[]"`
  instead of `"-"` for a record with no tags. `data/records.json`'s 5 accepted
  rows all currently have non-empty tags, so this path isn't exercised by the
  existing fixture, but it's a real gap the change introduces.
- **Defect found and folded in (not in the issue's notes):** adding `tags` to
  `REPORTED_FIELDS` breaks the summary line's truth: it would read "All 6
  reported fields are checked by the validation rules" while only 5 of the 6
  actually are (`tags` isn't in `VALIDATED_FIELDS`). This line is generated,
  not hand-written, so it silently becomes false the moment the column count
  changes. Confirmed no other test/file depends on its current exact wording
  (`grep` for "reported fields" / "checked by the validation" hit only
  `report.py` and the golden artifact).
- **Re-checked the issue's performance claim and it does not hold — corrected
  below and in the live issue.** `_table()` calls `_cell(row, field)` twice per
  row per field: once in the width pass (`max([len(field)] + [len(_cell(row,
  field)) for row in rows])`, `src/report.py:37`) and once again in the render
  pass (`out.extend(line([_cell(row, field) for field in REPORTED_FIELDS]) for
  row in rows)`, `src/report.py:49`) — 2×fields×rows `_cell` calls total, not
  "one width calculation for the whole run." Verified empirically by
  monkeypatching `_cell` with a counting wrapper and calling `render_report()`:
  50 calls at today's 5 fields × 5 accepted rows; 60 calls when simulating a
  6th (`tags`) field — a delta of 10 = 2×rows, exactly as expected. So adding
  `tags` adds O(rows) work in *each* of the two passes, the same order as the
  validator's own O(rows) per-record work — not "strictly cheaper." A
  secondary consequence for this plan specifically: because the tags-join
  happens inside `_cell()`, that join runs twice per row (once per pass)
  rather than once. Per the coordinator's direction this doesn't change the
  implementation approach — the row counts here are small enough that no
  caching/fast path is warranted — it only means the "strictly cheaper" claim
  must not be carried forward as confirmed. Corrected the live issue body via
  `gh issue edit 175` to state the real cost instead of the false claim.
- `tools/write_golden.py` regenerates `artifacts/report.golden.txt` via
  `python -m tools.write_golden`; `tests/test_golden.py` byte-compares against
  it.

## Changes

1. **`src/report.py`**
   - Add `"tags"` to `REPORTED_FIELDS`, appended last (after `currency`) since
     it's supplementary context, not a settlement-contract field.
   - `_cell(row, field)`: special-case `field == "tags"` — join the list with
     `", "` when non-empty, else `"-"`. Leaves the generic `_missing`/`str()`
     path untouched for every other field (no behavior change for them).
   - Fix the summary line so it stays true once `REPORTED_FIELDS` and
     `VALIDATED_FIELDS` diverge in length: change to
     `f"{len(validate.VALIDATED_FIELDS)} of {len(REPORTED_FIELDS)} reported
     fields are checked by the validation rules."` (5 of 6). `validate` is
     already imported.

2. **`artifacts/report.golden.txt`** — regenerate with
   `python -m tools.write_golden` after the code change lands.

3. **Tests** (new, must fail on current code before the fix):
   - `tests/test_report.py`: assert each accepted record's tags appear on its
     row, e.g. `"eu, high,priority, settled" in text` for `R-1001` (from
     `data/records.json`'s `"eu,\"high,priority\",settled"`), and that the
     `tags` header appears in the column header line.
   - `tests/test_report.py`: a direct unit test on `_table`/`render_report`
     for the empty-tags case — construct a `render_report(records=[...])` call
     with an explicit records list containing one accepted record with
     `"tags": ""` (or omit the key) and assert its rendered row cell is `"-"`
     wherever the tags column ends up, not `"[]"` or `"['']"`.
   - `tests/test_report.py`: assert the summary line reads
     `"5 of 6 reported fields are checked by the validation rules."` (replacing
     any prior implicit coverage of the old "All 5 reported fields" wording —
     confirmed no existing test asserts that exact string today).

## Out of scope

- `src/validate.py` / `src/parse.py` — untouched; `check_record()` and
  `parse_tags()` already do what's needed.
- `RIGHT_ALIGNED` — tags stays left-aligned (default), no change needed.

🔍 CP1 — re-read: `src/report.py` (`REPORTED_FIELDS`, `_cell`, `_table`,
`render_report`), `src/validate.py` (`check_record`, `VALIDATED_FIELDS`),
`src/parse.py` (`parse_tags`), `tools/write_golden.py`, `tests/test_report.py`,
`tests/test_golden.py`, `artifacts/report.golden.txt`, `data/records.json`; and
the actual issue #175 body (`gh issue view 175`), confirmed byte-identical to
the cached `tests/fixtures/t2/I1.md`. Gaps found & folded in: (1) `_cell()`
would render Python list repr for tags without a join/format fix; (2) empty
tags list not caught by `_missing()`, would render `"[]"` instead of `"-"`;
(3) the "All N reported fields are checked by the validation rules" summary
line becomes false once `tags` is reported-but-unvalidated — reworded to "5 of
6" instead of silently shipping a false claim; (4) **round-1 review
correction**: the issue's/plan's performance claim ("one width calculation for
the whole run", "strictly cheaper than the validator's per-record work") was
wrong — re-counted `_cell()` invocations empirically (50 → 60 calls, F=5→6,
R=5 rows fixed) and confirmed it's 2×fields×rows, i.e. O(rows) added work in
both the width pass and the render pass, same order as the validator. Live
issue #175 body corrected via `gh issue edit` to match; implementation
approach unchanged (no caching needed at this feed's size).

🔍 CP1 GATE — <pending>
