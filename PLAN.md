# PLAN — issue 108: Known flake section in README.md

## Re-measured state (real commands, real output)

- `python -m compileall -q src` → exit 0, clean.
- `python -m ruff check .` → `All checks passed!`, exit 0.
- `python -m pytest -q` → `31 passed in 0.23s`. Matches the issue's claim exactly; no correction
  needed to issue 108.
- `README.md` (current, full contents read) has no "Known flake" heading anywhere. It does
  mention in prose: "`CLAUDE.md` is the contract agents read: gates, layout, the committed
  artifact, and the known flake. `TESTING.md` maps areas to suites." — but no dedicated section,
  and no mention of `tests/test_flaky.py` by name.
- `TESTING.md` already carries a routing row: `| the known flake | tests/test_flaky.py | itself |
  see CLAUDE.md; gated on FACTORY_TESTBED_FLAKE |`.
- `CLAUDE.md` §"Known flake" (lines 47-58) is the canonical description: names
  `tests/test_flaky.py::test_rate_service_settles_within_the_retry_budget`, explains the
  `FACTORY_TESTBED_FLAKE` env var gate, and the CI-default (unset) determinism.

## Change

Single file: `README.md`. Add a new `## Known flake` section (heading text contains "Known
flake", satisfying the acceptance criterion literally) after the "Resetting" section and before
the closing `<!-- wording pass -->` comment. Content:

- Names `tests/test_flaky.py` explicitly.
- States it's gated by `FACTORY_TESTBED_FLAKE` (consistent with CLAUDE.md/TESTING.md wording,
  without duplicating the full explanation).
- Points the reader to `TESTING.md`'s routing table for the gating detail, satisfying "refers the
  reader to TESTING.md".

No other file changes. `src/` untouched (satisfies ruling #1 and the issue's own "No source file
under `src/` changes" criterion). `artifacts/report.golden.txt` untouched (ruling #2). No fixture
under `tests/fixtures/` touched (ruling #3).

## Judged against COMPLETE / ROBUST / FAULT-TOLERANT

- **Complete**: covers both acceptance bullets (heading text, naming the test file + pointing to
  TESTING.md) in one section; doesn't leave "refers to TESTING.md" implicit — it's an explicit
  markdown link/reference by filename.
- **Robust**: a pure markdown addition to a static file — no inputs, no edge cases, idempotent
  (re-running the edit is a no-op once applied; not literally re-appliable but there's no
  generation step to be non-idempotent about).
- **Fault-tolerant**: doesn't touch code paths; cannot break any gate. Will re-run all three gates
  after the edit to confirm `31 passed` still holds (it must, since no test file changes).

## Verification after edit

- `python -m compileall -q src`
- `python -m ruff check .`
- `python -m pytest -q` (expect `31 passed`, unchanged)
- Manual check: `README.md` contains a heading matching "Known flake", names
  `tests/test_flaky.py`, and references `TESTING.md`.

🔍 CP1 — re-read: `README.md` (full file), `TESTING.md` (full file), `CLAUDE.md` §"Known flake"
(lines 47-58), `tests/test_flaky.py` (full file), and issue 108's full body/acceptance criteria via
`gh issue view 108`. Gaps found & folded in: none — issue's claims matched actual gate output
exactly (31 passed, ruff clean, compileall clean), so no issue correction was needed.
