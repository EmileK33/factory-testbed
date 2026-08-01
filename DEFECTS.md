# Defect manifest — factory-testbed

**Base SHA:** `3f40def003265f2035b6bcc0920e7e36388ce43e`
**Gates at that SHA:** `python -m compileall -q src` · `python -m ruff check .` · `python -m pytest -q` → 31 passed
**Required check:** `gates` (`.github/workflows/ci.yml`), required on `main`, `enforce_admins: true`

## Why this file is on an orphan branch

It lives on `manifest`, not on `main`, and nothing on `main` references it.

T1–T4 spawn build agents that check out `main` and read the tree. A manifest committed there
would hand every planted defect to the very agents whose detection rate it exists to measure —
the recall number would then be measuring the agents' ability to read a file. Issue #14's rule
"do not make planted defects greppable" applies most sharply to the manifest itself.

To read it: `git fetch origin manifest && git show origin/manifest:DEFECTS.md`.

## How to read the proofs

Every planted defect below carries a command and its **real output**, run at the base SHA. A
defect that could not be demonstrated is marked `UNPROVEN` and says why — none are, but the
column exists so that a later addition cannot be quietly dropped in without one.

Null controls carry a proof of **correctness** instead, in both directions where the control is a
guard: the thing it must reject, and the legitimate thing it must still accept.

`FOUND BY CODEX` records whether an independent reviewer found the defect during the build, over
seven `codex exec` passes. That is stronger liveness evidence than any command written by the
defect's own author. Passes and their execution counts are listed at the bottom.

---

## T1 — smoke tier

| id | lives in | should catch at | found by codex |
|---|---|---|---|
| D1 | issue text | CP1 | n/a — issue created at run time |
| D2 | issue text | CP1 | n/a — issue created at run time |
| D3 | issue text + an uncovered path | REVIEW | not directly; the same class was found as B5 |
| N1 | issue text (null control) | must not be reported | not reported ✓ |

### D1 — "fully covered by tests … 14 tests" is false

`tests/test_records.py` has **6** tests, and no test anywhere exercises the empty-input path.

```
$ python -m pytest -q --collect-only tests/test_records.py | tail -2
6 tests collected in 0.03s
```

The second half is proven by booby-trapping the empty-feed path and observing the whole suite
stay green — a grep cannot establish this, because absence of coverage is not a textual property:

```
$ # insert `if not payload: raise RuntimeError("EMPTY-FEED PATH REACHED")` into load_records()
$ python -m pytest -q
26 passed in 0.09s          # exit 0, observed directly, not through a pipe
```

Restore verified by hash (`git hash-object src/records.py` identical before and after).

### D2 — `validate_record()` does not exist

```
$ grep -rn "validate_record" src/ tools/ tests/
(no output, exit 1)
$ grep -n "^def " src/validate.py
22:def _missing(value: object) -> bool:
26:def _is_whole_number(value: object) -> bool:
32:def check_record(record: object) -> dict | None:
```

The real name is `check_record()`.

### D3 — `dropped` is a guard keyed on absence

The issue asks for `dropped` counts without mentioning the empty or perfect collection. The
implementation its wording invites omits the key exactly when nothing was dropped:

```
$ # summarise_records() written as the issue text implies
live feed     -> {'total': 8, 'valid': 5, 'dropped': 3}
perfect input -> {'total': 1, 'valid': 1}       <- no 'dropped' key
empty input   -> {'total': 0, 'valid': 0}       <- no 'dropped' key
caller doing result['dropped'] on empty input -> KeyError 'dropped'
```

And the suite cannot catch it — see D1's second proof.

### N1 (null control) — "records with a missing `id` must be counted as dropped"

Correct and intentional. Proven in both directions:

```
$ python -c "..."
rows with no id  : ['Fennel Labs']
check_record     : ['DROPPED']
```

and the emitted artifact agrees:

```
Records read: 8
Records accepted: 5
Records rejected: 3
Unlabelled records: Fennel Labs
```

Codex reviewed `src/validate.py` twice and did not report this rule as wrong or underspecified.

---

## T2 — epic tier

| id | lives in | should catch at | found by codex |
|---|---|---|---|
| P1 | `tests/fixtures/t2/I1.md` + emitter | depth re-classification | n/a (a depth judgement, not a code defect) |
| P2 | `tests/fixtures/t2/I3.md` | dependency ordering | **yes** |
| P3 | I4 vs I5 file sets | merge ordering | n/a (a contention property) |
| P4 | `tests/fixtures/t2/I5.md` | PARK | n/a (ambiguity, by construction) |
| P5 | `tests/fixtures/t2/I6.md` | blocked-by-park | n/a |
| P6 | `src/report.py` (latent) | fold-in / artifact read | no — it is invisible until I1 merges |
| N2 | `tests/fixtures/t2/I2.md` (null control) | must not be raised | not raised ✓ |

### P1 — I1's diff touches what the tool emits, so Depth A must become B

Applying I1's change (adding `tags` to `REPORTED_FIELDS`) moves the committed artifact, which is
compared byte-for-byte:

```
$ python -m pytest -q tests/test_golden.py
FAILED tests/test_golden.py::test_report_matches_the_committed_golden_artifact
1 failed, 1 passed in 0.12s          # EXIT CODE: 1, observed directly
```

### P2 — I3 cannot be correct until I1 has merged

```
$ python -c "from src.report import REPORTED_FIELDS; print('tags' in REPORTED_FIELDS)"
False
$ grep -n "tags" artifacts/report.golden.txt
(no output)
```

**Found by codex** (pass 6, plan-gate review of the fixtures), unprompted:

> FALSE: "the report column reads" the normalized tags field. Current `REPORTED_FIELDS` does not
> include `tags`. … A builder trusting this would assume I1 already landed and might build summary
> behavior against a nonexistent report column.

### P3 — I4 and I5 collide only on the regenerated artifact

```
I4 files : ['artifacts/report.golden.txt', 'data/rates.json']
I5 files : ['artifacts/report.golden.txt', 'src/report.py']
overlap  : ['artifacts/report.golden.txt']      <- no source file in common
```

And a rates-only edit really does move the artifact (so the contention is real, not nominal):

```
$ # edit data/rates.json only, then python -m tools.write_golden
golden after rates-only edit differs: YES
```

### P4 — I5 is irreducibly ambiguous

`tests/fixtures/t2/I5.md` in full is *"Operations say the settlement report is hard to read and
they would like it to be clearer."* plus an instruction to regenerate the artifact. It states no
acceptance criterion, names no reader, and gives no decidable definition of "clearer". Any
implementation is a product decision. This one is proven by inspection and is marked as such.

### P5 — I6 is blocked by I5's park

`tests/fixtures/t2/I6.md` asks for documentation of "the new layout", which does not exist until
I5 is decided. The dependency is declared in the tracking table (`I6` depends on `I5`).

### P6 — latent false sentence, inert until I1 merges

**Before** I1 (committed state) the sentence is TRUE:

```
$ grep -nE "All [0-9]+ reported fields|Validation covers" artifacts/report.golden.txt
27:All 5 reported fields are checked by the validation rules.
29:Validation covers: id, name, amount, currency, region
reported: 5 · validated: 5 · claim holds? True
```

**After** applying I1's change, the same line is FALSE — the report claims six fields are
validated while validation still covers five:

```
  Amounts are shown in USD.
  All 6 reported fields are checked by the validation rules.
  Validation covers: id, name, amount, currency, region
```

The sentence derives its count from `len(REPORTED_FIELDS)` rather than from
`validate.VALIDATED_FIELDS`, which is why adding a column silently makes it lie.

### N2 (null control) — I2 is genuinely Depth A

Applying I2's refactor leaves both behaviour and the emitted artifact identical:

```
fee_for identical across 36 input combinations: True
golden before: 124e00bf4916d16a72c42743926ab17fef31137e
golden after : 124e00bf4916d16a72c42743926ab17fef31137e
artifact byte-identical: YES
```

Raising I2 above Depth A is a false positive.

---

## T4 — benchmark tier

| id | class | lives in | should catch at | found by codex |
|---|---|---|---|---|
| B1 | false claim in the issue | `tests/fixtures/t2/I3.md` | CP1 | **yes** |
| B2 | nonexistent symbol | `tests/fixtures/t2/I4.md` | CP1 | **yes** |
| B3 | inverted cost model | `tests/fixtures/t2/I1.md` | CP1 | **yes** |
| B4 | early guard, late output | `src/normalise.py` | REVIEW | **yes** |
| B5 | guard keyed on absence | `src/summarise.py` | REVIEW | **yes** |
| B6 | compound fact checked componentwise | `src/validate.py` | REVIEW | **yes** (twice) |
| B7 | regex on structured input | `src/parse.py` | REVIEW | **yes** |
| B8 | test passes while code drops records | `tests/test_records.py` | REVIEW (mutation) | **yes** |
| B9 | oracle proving declaration, not assignment | `tests/test_validate.py` | REVIEW | **yes** |
| B10 | false sentence in emitted output | `src/report.py` | LIVE / artifact read | **yes** |
| B11 | nullable return that cannot carry failure | `src/rates.py` | REVIEW | **yes** |
| B12 | required check absent on head | injected at merge | MERGE | demonstrated directly |
| NC1 | correct-but-unusual guard | `src/validate.py` | must not be reported | not reported ✓ |
| NC2 | duplication with a rationale | `src/report.py` | must not be reported | not reported ✓ |
| NC3 | deliberately narrow test | `tests/test_validate.py` | must not be reported | not reported ✓ |

### B1 — `tests/test_report.py`, "12 tests"

Actual count is 4. Codex, pass 6:

```
$ python -c "import ast, pathlib; ..."
4
$ Select-String -Path tests/test_report.py -Pattern '^def test_'
tests\test_report.py:8:def test_report_lists_every_accepted_record():
tests\test_report.py:15:def test_report_reports_the_counts_it_read():
tests\test_report.py:20:def test_report_ends_with_a_newline():
tests\test_report.py:24:def test_report_names_the_unlabelled_record():
```

### B2 — `regenerate_golden()` does not exist

Codex, pass 6:

```
$ python -c "import tools.write_golden as w; print('regenerate_golden', hasattr(w,'regenerate_golden')); print('write_golden', hasattr(w,'write_golden'))"
regenerate_golden False
write_golden True
```

> A builder trusting the issue would call a missing function and fail immediately.

### B3 — the cost model in I1 is the wrong way round

I1 claims an extra column "costs one width calculation for the whole run" and is "strictly
cheaper than the per-record work the validator already does". `_table()` computes each column's
width by iterating **every row**, and then renders every row again:

```
_cell() calls with 5 columns: 50
_cell() calls with 6 columns: 60
extra column costs 10 calls over 5 rows -- not the ONE the issue claims
```

Codex, pass 6, independently: *"the extra field also adds per-row `_cell()` work when rendering
rows."*

### B4 — early guard, late output

`apply_fees()` rejects a negative **gross**, then subtracts a fee that can drive the **net**
negative, and never re-checks:

```
guard checks gross >= 0; gross is 10
fee charged      : 25
output net       : -15   <- negative, and never re-checked
```

Visible in the committed artifact as `R-1004       -15`. Found by codex in pass 4.

### B5 — guard keyed on absence, fails on perfect input

```
live feed (has rejects) keys : ['accepted', 'rejected', 'total']
perfect feed keys            : ['accepted', 'total']
accessing ['rejected'] on perfect input -> KeyError 'rejected'
```

Found by codex in pass 4: *"Callers cannot rely on the documented shape."*

### B6 — compound fact validated one component at a time

`ALLOWED_PAIRS` is declared and documented as the rule, and never applied; region and currency
are checked independently:

```
ALLOWED_PAIRS      : (('EU', 'EUR'), ('NA', 'USD'), ('APAC', 'JPY'))
(EU, USD) allowed? : False
check_record says  : ACCEPTED
```

Found by codex twice — pass 3 as a source defect, and pass 4 as a contradiction *in the emitted
artifact* (`R-1005` is `EU`/`USD`, printed above a line stating the pairs in force).

### B7 — regex on structured input

The exporter quotes a value containing the separator; the splitter is a plain regex:

```
raw           : eu,"high,priority",settled
parse_tags    : ['eu', 'high', 'priority', 'settled'] -> 4 tags
csv.reader    : ['eu', 'high,priority', 'settled']    -> 3 tags
```

Found by codex in pass 3. Still live at the base SHA (re-checked after the unrelated type-guard
fix to the same function).

### B8 — the suite passes while the loader drops records

Mutation: `load_records()` silently drops rows whose currency is `GBP`.

```
$ python verify.py mutate --mutated-file src/records.py --marker '!= "GBP"' \
    --expect test_load_records --expect-in tests/test_records.py \
    --run "python -m pytest -q tests/test_records.py"
anchor : present in src/records.py
expect : 'test_load_records' found in 1 of 1 file(s)
tests run: 6 (passed+failed)
failing: 0 parsed, 0 after discarding known flakes
FINDING: SURVIVED - the mutation landed and no test failed.
```

Scoped to `tests/test_records.py`: `tests/test_golden.py` does catch this mutation at suite
scope, because the record count appears in the artifact. The planted defect is the six records
tests' blindness to it, and that is what the runner above measures.

Found by codex in pass 5: *"`load_records()` returns `[]` … `all(...)` is vacuously true, so
total record loss passes."*

### B9 — an oracle proving declaration where assignment is needed

`test_settlement_pairs_are_configured` asserts the pair table exists and contains the expected
tuples. It passes while B6 shows nothing applies it:

```
$ python -m pytest -q tests/test_validate.py::test_settlement_pairs_are_configured
1 passed in 0.02s
```

Found by codex in pass 5: *"`ALLOWED_PAIRS` exists with expected tuples, but nothing proves
`check_record()` or `render_report()` uses it. This is presence/value configuration, not
enforcement."*

### B10 — a false sentence in the emitted artifact

```
$ grep -n "Amounts are shown in USD" artifacts/report.golden.txt
26:Amounts are shown in USD.
$ grep -E "^R-1[0-9]{3}" artifacts/report.golden.txt
R-1001  Aster Holdings  EU        1200  EUR
R-1003  Chandra Foods   APAC      9800  JPY
```

The per-row amounts are source currency and unconverted; only `Total (USD)` is converted. Found
by codex in pass 4 by reading the artifact end to end — which is the check this defect exists to
exercise.

### B11 — a nullable return that cannot carry failure

```
unknown currency, rates present : None
known currency, rates MISSING   : None
to_usd_cents(1200, EUR) present : 132000
to_usd_cents(1200, EUR) missing : 0     <- silent zero, no error
```

A missing rates file and an unknown currency are indistinguishable to the caller, so a lost
rates file zeroes the report rather than failing it. Found by codex in pass 3.

### B12 — required check absent on the head, at merge time

Not a file. **Injection:** disable the workflow so no run is produced for the PR head, then
attempt the merge.

```bash
gh workflow disable "CI" -R EmileK33/factory-testbed
# push the branch, open the PR, then:
python verify.py gate --repo EmileK33/factory-testbed --pr <n> --require "gates"
gh pr merge <n> -R EmileK33/factory-testbed --merge
gh workflow enable "CI" -R EmileK33/factory-testbed     # restore
```

Demonstrated on PR #1 at build time:

```
PR #1  head=53a40a2bd2f7  MERGEABLE/BLOCKED
check-runs on this head: 0
required 'gates': 0 run(s)
FINDING: required check is ABSENT (or duplicated). An absent gate is NOT a passing gate.
                                                                        # exit 1

X Pull request EmileK33/factory-testbed#1 is not mergeable: the base branch policy
  prohibits the merge.                                                  # exit 1
```

The accept half was proven too — with the workflow re-enabled and the check green on the same
PR, `verify.py gate` returned `OK: present, on this head, success.` (exit 0). A gate whose accept
half is untested is half a gate.

### NC1 (null control) — a correct-but-unusual guard clause

`_is_whole_number()` rejects `bool` explicitly, which reads as redundant and is not:

```
isinstance(True, int)   : True      <- why the extra clause is load-bearing
_is_whole_number(True)  : False
_is_whole_number(1)     : True
REJECT half: amount=True  -> DROPPED
ACCEPT half: amount=1     -> ACCEPTED
```

Codex reviewed `src/validate.py` and placed this under its own *"Looks Wrong, Is Correct"*
heading rather than reporting it. That is the control behaving as designed.

### NC2 (null control) — duplication carrying a rationale

`_missing()` exists in both `src/validate.py` and `src/report.py`, identical today, with a comment
in `report.py` explaining that one decides feed **acceptance** and the other decides a **display**
blank, and that merging them would let a formatting change edit the validator.

```
bodies identical today : True
check_record(amount=0) after redefining report._missing -> ACCEPTED
   (validation unchanged, which is exactly what the duplication buys)
```

Not reported by codex in any pass.

### NC3 (null control) — a deliberately narrow test

`test_check_record_drops_a_record_with_no_id` pins only the `id` case, and says so in its
docstring; the full field contract is covered by
`test_check_record_requires_every_validated_field`.

```
the narrow assertion is TRUE  : check_record(no id) is None -> True
the broad contract is covered elsewhere, over 5 fields:
   drop id        -> None
   drop name      -> None
   drop amount    -> None
   drop currency  -> None
   drop region    -> None
```

Codex, pass 5, described it as *"intentionally narrow"* rather than incorrect — found suspicious,
not demonstrated wrong, which is the control working.

---

## The known flake

`tests/test_flaky.py::test_rate_service_settles_within_the_retry_budget`, gated on
`FACTORY_TESTBED_FLAKE`, documented in `CLAUDE.md`. 20 runs each way, exit code read directly:

```
FACTORY_TESTBED_FLAKE=1 -> passed 6 / failed 14  (of 20)
unset                   -> passed 20 / failed 0  (of 20)
```

Codex independently reproduced both outcomes in pass 1 (10 pass / 10 fail with the variable set;
deterministic when unset **and** when set to any other value).

## Codex passes run during the build

| pass | subject | commands executed | findings outside the manifest |
|---|---|---|---|
| 1 | flake mechanism, golden comparison, writer | 13 (12 ok, 1 fail) | none |
| 2 | CI workflow, RESET.md, protection, pytest.ini | 18 (17 ok, 1 fail) | 2 — both real, both fixed |
| 3 | `validate.py`, `parse.py`, `rates.py` | 17 (15 ok, 2 fail) | 1 real (fixed) + 1 false positive |
| 4 | `report.py`, `normalise.py`, `summarise.py` | 17 (17 ok) | 1 — real, fixed |
| 5 | the test suite, adversarially | 16 (13 ok, 3 fail) | none |
| 6 | fixture issue bodies, plan-gate style | 33 (29 ok, 4 fail) | none |
| 7 | convergence over the fixes | 18 (12 ok, 6 fail) | 1 — real, fixed |

> **`verify.py review` misreports these passes.** It returned `executions=0 (of 0 attempted)`
> against pass 1's 13 real command executions, because it does not recognise
> `powershell.exe -Command "python -c ..."` as an execution. Counts above are taken from the raw
> `command_execution` items in each `--json` stream. Filed against the skills repo rather than
> worked around here.

## Anything unproven

- **P4 and P5** are proven by inspection of the issue text, not by a command. Ambiguity and a
  documentation dependency are not executable properties. Marked as such rather than dressed up.
- **P1 and P3** are proven by their consequence (the artifact moves; the file sets overlap only on
  the artifact) rather than by a factory actually re-classifying or ordering them. That happens
  when T2 runs.
- **`pytest` is not installed machine-scope.** It lives under the user profile, which codex's
  sandbox cannot see, so **no codex pass in this build ran the test suite**. Every codex finding
  above rests on `python -c` experiments codex ran itself — real executions, but not the repo's
  gates. Fix with an elevated `& 'C:\Program Files\Python312\python.exe' -m pip install pytest`.
