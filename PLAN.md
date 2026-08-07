# PLAN — #154: header + underline for "Net after fees"

(Note: this worktree's `PLAN.md` on disk matched `main`'s stale content from
issue #151's build — `1c84227`/`309d66e` both checked in a `PLAN.md` for their
own item. That content is irrelevant here; this file replaces it.)

## Re-measurement against actual current source

Read `src/report.py` in full on `negctl-park-154` (branched from current
`main`, i.e. after `#152`'s tags column and `#151`'s `fee_for()` split — both
merged, neither touches this section). Specifically `_table()` (lines 41-56)
and the `Net after fees` block in `render_report()` (lines 76-80):

```python
lines.append("Net after fees")
lines.append("--------------")
for row in apply_fees(accepted):
    lines.append(f"{row['id']}  {row['net']:>8}")
lines.append("")
```

`_table()`'s style: for each field, `width = max(len(field_name), max(len(cell)
for cell in that column))`; header and underline (`"-" * width`) cells are
`ljust`/`rjust` per field (right-aligned only for fields in `RIGHT_ALIGNED`,
e.g. `amount`); all cells joined with `"  "`, line right-stripped.

**Issue correction filed:** the issue's quote of the main header — `` `id  name
region  amount  currency` `` — omitted `tags`. `REPORTED_FIELDS` is
`("id", "name", "region", "amount", "currency", "tags")` (`src/report.py:16`),
confirmed against the live `artifacts/report.golden.txt` line 4 (`id      name
region  amount  currency  tags`). Corrected via `gh issue edit 154` (added
`tags` to the quoted header) and logged the correction + reasoning as a
comment on the issue. No other factual claim in the issue is wrong: the "no
header row today" claim, the `<id>  <net>` per-record shape, and the `amount`
right-alignment reference all check out against the current code as written.

## One judgment call, resolved and documented (not a park)

**Revision note:** the first version of this plan hardcoded the header's `id`
cell to its literal 2-character width (`"id"`) and only right-justified `net`
to width 8. codex caught a real defect in that version, independently
re-verified here by computing column indices against the live feed
(`src/records.py` → `apply_fees()`, ids `R-1001`..`R-1005`, all 6 chars):

```
header (broken):  'id' + '  ' + 'net'.rjust(8)              = 'id       net'
data (unchanged): 'R-1001' + '  ' + '995'.rjust(8) (via :>8) = 'R-1001       995'
```

`"id"` is 2 chars but the real `id` values are 6 chars, so the header's
2-space separator lands 4 columns left of the real one — `net`'s label sits
at column 13, while the real net field starts at column 8 (digits anywhere in
columns 8-15 depending on value width). Confirmed by rendering the live feed
and inspecting column indices directly (see script output below), not just
visually — for every id in the feed the header's `net` label ends up left of
the data.

The issue's literal example text `` `id  net` `` (bare, 2-space gap) is
illustrative of the *shape* (word, gap, word), not a byte-exact string — it
can't be, since the real id width is data-driven and unknown at spec-writing
time. **Fixed resolution:** compute the `id` column's width the same way
`_table()` computes column widths — from the actual data in this section —
instead of from the header word's own length:

```python
net_rows = list(apply_fees(accepted))
id_width = max([len("id")] + [len(str(row["id"])) for row in net_rows])
```

(mirrors `_table()`'s own width formula, `src/report.py:42-45`; well-defined
when `net_rows` is empty — `id_width == len("id") == 2`.) Then:
- **`id`** (left-aligned, "matching the main table's ... left-aligned style
  for `id`"): header cell `"id".ljust(id_width)`, underline cell
  `"-" * id_width`, and — the part the first version got wrong — the **data**
  cell also becomes `str(row["id"]).ljust(id_width)` instead of the bare
  `row['id']` used today.
- **`net`** (right-aligned, "consistent with how the main table already
  right-aligns `amount`"): unchanged from the first version — header cell
  `"net".rjust(8)`, underline `"-" * 8`, data cell stays `row['net']:>8`,
  reusing the fixed width the per-record line already commits to.

Re "the existing per-record lines are otherwise unchanged": padding `id` with
`ljust(id_width)` looks like it touches the data line, but `id_width` is the
max over the *same* rows being rendered, so for every id actually present
it's a no-op. Verified directly, not just reasoned about — rendered the live
feed with both formatters and diffed:

```
old = [f"{r['id']}  {r['net']:>8}" for r in net_rows]
new = [f"{str(r['id']).ljust(id_width)}  {r['net']:>8}" for r in net_rows]
old == new   # True, measured against the live feed
```

Concretely, insert (`net_rows` computed once, reused by the loop):

```python
lines.append("Net after fees")
lines.append("--------------")
net_rows = list(apply_fees(accepted))
id_width = max([len("id")] + [len(str(row["id"])) for row in net_rows])
lines.append(f"{'id'.ljust(id_width)}  {'net'.rjust(8)}")
lines.append(f"{'-' * id_width}  {'-' * 8}")
for row in net_rows:
    lines.append(f"{str(row['id']).ljust(id_width)}  {row['net']:>8}")
```

Character-by-character check against the live feed (`id_width` resolves to
6): header `'id           net'`, underline `'------  --------'`, first data
row `'R-1001       995'` — the `net` label's right edge (header, col 15) and
every data row's right-justified field (cols 8-15) now share the same right
boundary; the header's `net` label sits directly above the numeric column
instead of 4 columns to its left.

## Implementation steps

1. In `src/report.py`, replace the `Net after fees` block (the four lines
   quoted at the top of "Re-measurement") with the version in the previous
   section: compute `net_rows` and `id_width` once, emit the header and
   underline, then loop emitting `str(row['id']).ljust(id_width)` instead of
   bare `row['id']`. No other line in `render_report()` or `_table()` changes.
2. Regenerate the golden artifact: `python -m tools.write_golden`. Diff it to
   confirm only the two new lines appear and every per-record `id  net` row is
   byte-identical to before (verified above by direct comparison against the
   live feed — `id_width` resolves to 6, matching every id's actual length,
   so `ljust(6)` is a no-op for all five accepted records).
3. Extend `tests/test_report.py`:
   - `test_net_after_fees_has_a_header_and_underline` — render the report,
     locate the `"Net after fees"` line, assert the next two lines are
     exactly `"id           net"` and `"------  --------"` (widths from the
     live feed's `id_width == 6`).
   - `test_net_after_fees_columns_align_with_the_header` — for each accepted
     record's rendered line in that block, assert its length equals the
     header's length and that the trailing 8 characters (the `net` field)
     line up under the header's right-justified `net` label — i.e. don't just
     re-assert the formula, check the actual rendered column positions the
     way codex's finding did.
   - `test_net_after_fees_net_values_are_unchanged` — assert each accepted
     record's line still ends with `f"{net:>8}"` and starts with
     `str(id).ljust(id_width)`, computed independently via `apply_fees()` in
     the test (same pattern the file already uses in
     `test_report_lists_every_accepted_record`).
   Checked via grep: no existing test asserts on the "Net after fees" block's
   exact shape today — only `tests/test_golden.py` touches it, indirectly,
   through the byte-for-byte artifact comparison. These are net-new coverage.
4. Run the three repo gates and fix anything they surface.

## Gates (after implementation)

```
python -m compileall -q src
python -m ruff check .
python -m pytest -q
```

## Two places I'd attack next (adversarial)

1. `net`'s width is still the fixed 8 read off the current format string, not
   computed from data — if a future `net` value ever needs more than 8
   characters (unlikely given cents-based ints, but not enforced anywhere),
   the header stays aligned but the data column would silently overflow its
   padding. `id`'s width no longer has this problem (now data-driven via
   `id_width`), but `net` still does; same latent risk already existed in the
   unmodified per-record line, not introduced by this change, but worth a
   second look since the header now visually promises an alignment the
   fixed-width format doesn't strictly guarantee for arbitrarily large values.
2. Re-diff `artifacts/report.golden.txt` after regenerating
   (`git diff --stat`) to positively confirm only the two intended new lines
   changed and every per-record line's `id` field is still byte-identical
   (not just numerically equal-looking) — since `id_width` is now computed
   from data rather than hardcoded, a bug in that computation (e.g. an off-by
   caused by an unaccepted/rejected record leaking into `net_rows`) would
   silently shift every id's padding by the same amount and could still look
   plausible without a byte-for-byte check.

---

🔍 CP1 — re-read: `src/report.py` in full (`_table()` lines 41-56, `_cell()`,
`REPORTED_FIELDS`/`RIGHT_ALIGNED`, and the `Net after fees` block in
`render_report()` lines 76-80), `src/normalise.py::apply_fees()` (confirms
`id` passes through unchanged, `net` is `amount - fee_for(record)`),
`artifacts/report.golden.txt` (current committed golden, confirmed 6-field
header including `tags`), `tests/test_report.py` (confirmed no existing test
pins the "Net after fees" block's exact text), `tests/test_golden.py`,
`tools/write_golden.py`; specification: `gh issue view 154` (live)
cross-checked against cached `ITEM-ISSUE.md` (identical). Also re-verified the
live feed directly via `python3` (`src.records.load_records()` →
`check_record()` → `apply_fees()`) to get real `id`/`net` values rather than
reasoning from the golden file alone.

Gaps found & folded in: (1) issue's quoted main-table header omitted `tags` —
corrected via `gh issue edit 154` + logged comment; (2) first draft of this
plan hardcoded the header's `id` cell to its literal 2-character width, which
codex flagged (BLOCKING) as misaligned against real ids (`R-1001` etc., 6
chars) — independently re-derived the column arithmetic against the live feed,
confirmed the defect, and replaced the fixed width with `id_width` computed
from `net_rows` the same way `_table()` computes column widths from data,
applying it to both the header/underline **and** the per-record `id` cell
(verified the per-record change is a byte-for-byte no-op for the current data
by rendering old vs. new formatters and diffing); (3) issue's literal header
example `id  net` would still misalign with the data's fixed 8-width `net`
column if taken byte-literally — resolved by deriving the `net` cell's width
from the existing `:>8` format rather than the literal example string,
documented above rather than silently guessed; (4) no test currently pins the
"Net after fees" block's shape — folded in three new tests covering the
header/underline text, actual rendered-column alignment (not just the
formula), and byte-unchanged net values.

🔍 CP1 GATE — pending.
