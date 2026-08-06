# Agent report — issue #79

## Verdict

Done. PR opened: https://github.com/EmileK33/factory-testbed/pull/90 (`t2/i7-feed-fix` -> `main`).
`data/records.json` R-1007 currency `GBP`→`EUR`, R-1008 amount `"n/a"`→`720`. Fennel Labs
untouched, still rejected, no `id` invented (re-verified via `check_record()` over
`load_records()`: only `Fennel Labs` rejects post-fix). `tests/test_pipeline.py`'s coupled
assertion updated (accepted 5→7, rejected list → `["<unlabelled>"]`). `artifacts/report.golden.txt`
regenerated via `python -m tools.write_golden`; every value checked against figures recorded
during planning before trusting it (accepted 7, rejected 1, Total USD 6019.66, R-1007 net 519,
R-1008 net 659) — all matched exactly. No changes to `src/validate.py`/`src/records.py`/
`src/report.py`.

Step 1 re-measurement: every factual claim in issue #79 checked out against the real tree
(details on the PR). Issue body **not edited** — nothing false found. Plan gate: round 1
BLOCKING on a blanket "no other tests move" claim (three actually move); round 2 PASS, no new
findings.

## Gates

- type-check (`python -m compileall -q src`): PASS
- lint (`python -m ruff check .`): PASS
- tests (`python -m pytest -q`): PASS — 41 passed, 1 xfailed (same known `parse.py` quoted-tag
  xfail as baseline, unrelated to this change)
- Test files that FAILED TO COLLECT: none

## Blockers

None.

## Report path

`D:\scratch\factory\t2-82\worktrees\79\AGENT-REPORT.md`

## Where I'd attack this next

1. **The golden-value hand-verification is eyeball-only, not asserted in code.** I checked the
   regenerated `artifacts/report.golden.txt` against the recorded expected values by reading the
   file, but nothing in the test suite pins the specific numbers 7/1/6019.66/519/659 beyond the
   byte-for-byte golden compare and `test_summarise_counts_the_feed_it_was_given`'s two literals.
   A reviewer could push on whether those two are a strong enough pin, or whether the byte compare
   alone is doing all the real work.
2. **`data/rates.json`'s EUR rate (11000 bp) is taken as given, not independently sourced.**
   R-1007's USD contribution to the total depends on it; I trusted the existing committed rate
   file rather than re-deriving or cross-checking it against any external source, since the issue
   didn't flag it and it's out of scope — but it's the one number in this change I didn't
   independently verify from first principles.
