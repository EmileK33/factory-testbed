# PLAN — issue #228: Count accepted records by tag

## Re-measurement (requirement 1)

- `src/summarise.py::summarise()` exists today (confirmed by `Read`) and currently returns only
  `{"total": ..., "accepted": ..., "rejected": [...] (if any)}`. It calls
  `src.validate.check_record(record)` per record but only tests the result for `None`/not-`None`
  — it discards the normalised dict, including the `tags` list, entirely.
- `src.validate.check_record()` (`src/validate.py:32`) returns a normalised dict whose `"tags"`
  key is `parse_tags(record.get("tags", ""))` (`src/validate.py:62`) — confirmed by reading the
  function body. So "the same normalised field the report column reads" is accurate:
  `src/report.py:769` builds its `accepted` list the same way
  (`[checked for checked in (check_record(row) for row in raw) if checked]`), and each row's
  tags cell is that same `checked["tags"]` list, not a re-split of the raw column.
- Ran `python3 -m pytest -q --collect-only tests/test_report.py` → **74 tests collected**, not
  12 as the issue stated. Filed as a correction on the GitHub issue (see report). The `12` in the
  original text was almost certainly a mix-up with `tests/test_tags.py`'s
  `assert len(KNOWN_TAGS) == 12`. This does not change anything about the plan below — this
  item's diff does not touch `src/report.py` — it only means the "well protected" claim should be
  read as "protected by a 74-test suite," and the specific number is not load-bearing for this
  item either way.
- Ran the feed through `check_record()` directly to know the expected shape of `by_tag` on the
  committed fixture (`data/records.json`, 8 records):
  ```
  R-1001 ['eu', 'high', 'priority', 'settled']
  R-1002 ['na', 'settled']
  R-1003 ['apac', 'bulk']
  R-1004 ['na', 'small']
  R-1005 ['eu', 'crossborder']
  ```
  (the sixth record, "Fennel Labs", is missing `id` → rejected/unlabelled; R-1007's currency
  `GBP` is not in `CURRENCY_CODES` — rejected; R-1008's amount `"n/a"` is not a whole number —
  rejected. This matches
  `tests/test_counts.py::test_summarise_counts_the_feed_it_was_given`'s `accepted == 5` and
  `rejected == ["<unlabelled>", "R-1007", "R-1008"]`.)
  So the expected `by_tag` on the committed fixture is:
  `{"eu": 2, "high": 1, "priority": 1, "settled": 2, "na": 2, "apac": 1, "bulk": 1, "small": 1,
  "crossborder": 1}`.
- Confirmed `summarise()`'s only other caller in the repo besides `tests/test_counts.py` is
  `tools/write_golden.py` — checked, and that module does **not** call `summarise()` at all (it
  calls `check_record()` directly for its own row-matching). `grep -rln "summarise" --include=*.py .`
  returns only `src/summarise.py`, `tests/test_counts.py`, `tools/write_golden.py` (the last is a
  false positive: the actual match is `tools/write_golden.py:149: def summarise_artifact() -> str:`
  — a differently-named function, not a call to `src.summarise.summarise()` and not a docstring
  reference to counting as an earlier draft of this plan mis-stated). So adding a new key to
  `summarise()`'s return dict is additive and has exactly one existing consumer to keep green:
  `tests/test_counts.py`.
- `TESTING.md` routes "counting" → `src/summarise.py` → `tests/test_counts.py`, coupled to
  `data/records.json`. No golden-artifact coupling for this file (that's `report.py`'s row).
- No written spec beyond `ITEM-ISSUE.md` (re-read in full above) and `RULINGS.md` (re-read in
  full: **5** standing rulings, R1–R5, echoed here and in every report).

## What will change

**`src/summarise.py::summarise()`** (only file touched):

- Capture `check_record(record)`'s return value instead of discarding it.
- When it is not `None` (accepted), also fold its `"tags"` list into a `by_tag: dict[str, int]`
  accumulator — **one increment per unique tag PER RECORD**, i.e. `for tag in set(checked["tags"])`,
  not `for tag in checked["tags"]`. This is a correction from an earlier draft of this plan, which
  chose plain occurrence-counting and was wrong: the issue's own words are "a mapping from each
  tag to the number of accepted records carrying it" — that is a record count, not an occurrence
  count. `check_record()`/`parse_tags()` do not dedupe (`parse_tags("na,na")` really does return
  `["na", "na"]`, confirmed by running it), so a record whose raw `tags` column repeats the same
  tag (e.g. `"na,na"`) must still only add 1 to `by_tag["na"]`, not 2. Deduping *within one
  record's already-split list* before counting is not "re-splitting the raw column" (the thing the
  issue says not to do) — it is exactly the counting decision the issue is asking `summarise()` to
  make; `parse_tags()`'s own output is left untouched, `check_record()` is not re-implemented, and
  no field is re-derived from the raw string.
- Add `by_tag` to the returned dict unconditionally (always present, even as `{}` for an empty or
  all-rejected feed) — unlike `rejected`, which is conditionally omitted when empty. Rationale:
  `rejected`'s omission is an existing, separate convention already relied upon by
  `tests/test_counts.py` (no assertion on its absence, but changing that convention is out of
  scope); `by_tag` is a new key with no existing convention to match, and "always present, maybe
  empty" is simpler and more robust (a caller doing `counts["by_tag"]` doesn't need a `.get()` +
  default) than "sometimes present." I will keep this key unconditional both for a feed with zero
  accepted records and for a feed where every accepted record has zero tags.

## Tests

- `tests/test_counts.py` (existing, single test) — will extend it to assert the exact `by_tag`
  mapping computed above against the committed fixture, alongside the existing `total`/`accepted`/
  `rejected` assertions, so the suite continues to describe the real fixture end-to-end in one
  place (matches this file's existing "coupled to `data/records.json`" docstring convention).
- A new small unit test (in `tests/test_counts.py`) with a synthetic records list covering:
  - a record carrying multiple distinct tags → each tag counted once,
  - two accepted records each carrying the same tag once → counted twice (this alone does NOT
    distinguish occurrence-counting from record-counting — see below — so it is necessary but not
    sufficient),
  - **a single accepted record whose raw `tags` column repeats one tag (e.g. `"na,na"`, which
    `parse_tags()` returns as `["na", "na"]`, confirmed by direct measurement above) → `by_tag`
    must show `1` for that tag from that record, not `2`.** This is the case that distinguishes
    record-counting (correct, per the issue's own wording) from occurrence-counting (the bug the
    gate caught in this plan's first draft) — a naive `for tag in checked["tags"]:` implementation
    fails this specific assertion while a `for tag in set(checked["tags"]):` implementation passes
    it; no other planned test tells the two apart, so this one is load-bearing on its own, not
    redundant with the cross-record case above.
  - combining both: one accepted record with an internally-duplicated tag (`"na,na"`) and a second
    accepted record carrying `"na"` once → `by_tag["na"] == 2` (one from each record), not `3`
    (which occurrence-counting across both records would produce) and not `1` (which a
    once-per-tag-globally bug would produce) — this closes the gap the gate flagged even under
    combination, not only in isolation.
  - a rejected record's tags are NOT counted (proves `by_tag` only counts accepted records, not
    merely "any record with tags"),
  - an accepted record with no tags (empty `tags` list) → contributes nothing, `by_tag` stays
    correct and no `""`/empty key appears,
  - a fully-rejected list → `by_tag == {}` (not omitted, not `None`) — this one already
    distinguishes "always present" from "omitted when empty" by asserting on key presence
    directly, not merely on value, so it is not a member of the same oracle-indistinguishable
    class as the duplicate-tag finding.
- Per requirement 2b, each new/changed assertion will be verified against a real mutation of
  `src/summarise.py` (e.g. mutating the tag-counting increment or the accepted-branch guard) using
  `verify.py mutate`, with `--junit-xml`, before this is reported done — done in the code phase,
  not here. The within-record-duplicate test above will specifically be proved to kill a mutation
  that reverts `set(checked["tags"])` back to plain `checked["tags"]` (occurrence-counting), since
  that is the exact wrong implementation the gate demonstrated slips past every other planned test.

### Sweep for other oracle-indistinguishable cases (gate finding class, requirement 4)

Re-examined every planned assertion above for the same shape — "does a plausible wrong
implementation also pass this test?" — not just the duplicate-tag one the gate found:

- **Cross-record tag sharing** (two records, one tag each): occurrence-counting and
  record-counting agree here (2 records × 1 occurrence each = 2 either way), so this test cannot
  and does not need to distinguish them — it only proves basic accumulation works, which is a
  separate, real requirement. Not a gap; correctly scoped to what it tests.
- **Rejected record's tags excluded**: a wrong implementation that counted ALL records (not just
  accepted ones) is a different bug from occurrence-vs-record counting, and this test is the one
  that would catch it — confirmed it targets a distinct failure mode, not the same one already
  covered elsewhere.
- **Empty-tags record contributes nothing**: distinguishes "iterate and add nothing" from a buggy
  implementation that inserts an empty-string key or a zero-count key; a wrong implementation
  that does either fails this test specifically. Not the same class as the duplicate-tag gap.
- **Always-present vs. omitted `by_tag`**: already addressed above — this test asserts on key
  presence, not just value, so "omit when empty" and "always present, empty dict" produce
  different, distinguishable outcomes under this assertion.
- **Multiple distinct tags on one record**: a wrong implementation that only recorded the LAST tag
  seen per record (e.g. via a bug that overwrites rather than accumulates) would fail this test,
  since it asserts every distinct tag is present with count 1 — this is a real, distinct failure
  mode from the duplicate-tag one and this test is what catches it.

No other case in the current test list was found where two plausible implementations both pass —
the duplicate-tag case (now fixed above, with a dedicated discriminating test) was the only
member of that class found on this sweep.

## Verification plan (code phase, after go-ahead)

1. Gates: `python3 -m compileall -q src`, `python3 -m ruff check .`, `python3 -m pytest -q`.
2. Routed suite per `TESTING.md`: `tests/test_counts.py` (this item's area). Also re-run
   `tests/test_report.py tests/test_golden.py` as a sanity check that an untouched file's suite
   stays green (it should, since `src/report.py` is not edited) — this also directly answers the
   CP2 "uncovered" field with evidence rather than assumption.
3. Mutation kills against `src/summarise.py` via
   `python C:\Users\emile\.claude\skills\factory\verify.py mutate --mutated-file src/summarise.py --marker <id> --expect <test> --junit-xml <path>`
   for each of: the `by_tag` increment line, the `set(...)` dedup around the increment (reverting
   to plain `checked["tags"]` occurrence-counting — must be killed by the within-record-duplicate
   test above), the accepted-record guard, and the always-present-key behavior (mutate it to
   conditional-omit-when-empty and confirm a test kills that).
4. No change to `src/report.py` or `artifacts/report.golden.txt` is anticipated, so
   `python3 -m tools.write_golden` should not be needed; if any surprise diff to the golden
   artifact shows up in `git status` after implementation, that is a signal something touched
   `report.py`'s output unexpectedly and needs investigating before proceeding, not a routine
   regen step for this item.

🔍 CP1 — re-read (round 2, after gate round 1 BLOCKING verdict): `src/summarise.py::summarise()`,
`src/validate.py::check_record()` (line 32, return dict at line ~57-63), `src/parse.py::parse_tags()`
(re-ran it directly on `"na,na"` this round: confirmed it returns `["na", "na"]`, undeduplicated),
`src/report.py` lines 1-40 and 764-770 (`REPORTED_FIELDS`, `LIST_VALUED_FIELDS`, `render_report()`'s
`accepted` construction), `tools/write_golden.py` (re-checked the `summarise` grep hit directly:
`tools/write_golden.py:149: def summarise_artifact() -> str:`, not a docstring reference as an
earlier draft wrongly stated), `tests/test_counts.py` (full file, 1 test), `TESTING.md`,
`data/records.json` (full file, 8 records), plus a real `check_record()` run over the fixture to
get exact expected tag counts; and `ITEM-ISSUE.md` (full text, re-read again this round, specifically
the phrase "a mapping from each tag to the number of accepted records carrying it") — no other
written spec exists for this item. Gaps found & folded in: (1) issue's "12 tests" claim for
`tests/test_report.py` re-measured as false (actual: 74) — corrected on the GitHub issue, does not
change the plan since this item never touches `report.py`; (2) issue is silent on whether `by_tag`
should be present-but-empty vs. omitted for a tag-free/record-free feed — resolved (always present)
with rationale, and the planned test asserts on key presence so the two readings are distinguishable;
(3) **round-1 gate BLOCKING finding, now fixed:** the previous draft chose occurrence-counting for
duplicate tags within one record and could not tell it apart from record-counting in its own test
suite — re-read the issue's exact wording ("number of accepted records carrying it") and switched
the implementation plan to `set(checked["tags"])`-based per-record deduplication, plus added a
test specifically constructed so a `"na,na"`-style record distinguishes the two readings (asserted
`1`, not `2`), and a combined within-record + cross-record test so the fix holds under composition,
not just in isolation; (4) **non-blocking correction folded in:** the caller-survey grep hit against
`tools/write_golden.py` was mis-described as "a docstring reference to counting" — the real match
is the `summarise_artifact()` function definition; the underlying conclusion (it does not call
`summarise()`) was and remains correct, only the stated evidence was wrong, now corrected; (5) swept
every other planned assertion for the same "two plausible implementations both pass" shape per the
gate's request — findings recorded in the new "Sweep for other oracle-indistinguishable cases"
section above; no further instance found.
