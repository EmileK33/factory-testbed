# Defect manifest — factory-testbed

**Base SHA:** `f37a337afe002c839ff285e87731e88b389a93ba`
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

> **Corpus era: `T2-epic.md` at `b130717` or later — the NINE-item corpus.** Recorded because this
> section was twice left describing a corpus two revisions behind (`#75`), and a run scored against
> a stale key gets a confident wrong answer rather than a gap. Check with
> `git log -1 --format=%h -- skills/factory/tests/T2-epic.md` and, if it names an earlier commit
> than `b130717`, **this section does not describe the tier you are running.**
>
> What changed and when, so a future divergence is legible rather than mysterious:
> `#26` added I7 and re-pointed I6's edges, moving **P3 from I4×I5 to I4×I7**; `#59` added I8 and I9
> to give wave 3 three unequally-overlapping siblings, adding **P8a/P8b/P8c**. Item count, wave
> composition and spend all moved at each step, so T2 results compare only within one era.

| id | lives in | should catch at | found by codex |
|---|---|---|---|
| P1 | `tests/fixtures/t2/I1.md` + emitter | depth re-classification | n/a (a depth judgement, not a code defect) |
| P2 | `tests/fixtures/t2/I3.md` | dependency ordering | **yes** |
| P3 | **I4 vs I7** file sets | merge ordering / contention | n/a (a contention property) |
| P4 | `tests/fixtures/t2/I5.md` | PARK | n/a (ambiguity, by construction) |
| P5 | `tests/fixtures/t2/I6.md` | blocked-by-park | n/a |
| P6 | `src/report.py` (latent) | fold-in / artifact read | no — it is invisible until I1 merges |
| **P8a** | `tests/fixtures/t2/I8.md` + `src/records.py` | merge **ordering** (wave 3, merges FIRST) | not yet run |
| **P8b** | `tests/fixtures/t2/I9.md` + `src/summarise.py` | merge **ordering** (wave 3, merges LAST) | not yet run |
| **P8c** | `tests/fixtures/t2/I3.md` + `src/summarise.py` | merge **ordering** (wave 3, the MIDDLE) | not yet run |
| N2 | `tests/fixtures/t2/I2.md` (null control) | must not be raised | not raised ✓ |
| **U1** | `src/validate.py` (**UNPLANTED**, pre-existing) | any reviewer reasoning about rejections | not yet run |

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

### P3 — I4 and I7 collide only on the regenerated artifact

**Re-pointed from I4×I5 by `#26`, and the reason is the important part:** P4 requires I5 to **park**
on ambiguity, and the better the factory behaves the earlier that park lands — at re-measurement,
before `PLAN.md`, producing no plan, no branch, no PR and **no diff**. So P3's subject disappeared
exactly when P4 succeeded, and the two plants were scoring each other. I7 is the half parking cannot
remove: same artifact, disjoint source, concrete enough that parking it would itself be a defect.

```
I4 files : ['artifacts/report.golden.txt', 'data/rates.json']
I7 files : ['artifacts/report.golden.txt', 'data/records.json']
overlap  : ['artifacts/report.golden.txt']      <- no source file in common
```

Both items are **data** corrections that re-emit the same committed artifact, which is what makes
the contention real rather than nominal, and what makes it invisible to any check comparing *source*
paths. Score the **disjointness**, not the literal list: a correct fix may reach a path this file did
not predict.

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

### P8a / P8b / P8c — wave 3's three siblings, with UNEQUAL overlaps

Added by `#59`. Before it, wave 3 held one item and **every earlier version of this tier scored H2
with a denominator of zero** — `run-wave` Phase D states the ordering rule as *"Merge order for
**N>2** PRs"*, so with two it does not engage at all, and two siblings always overlap symmetrically.

The profile the three must produce, **confirmed at run time from the real diffs, never from the
issue bodies**:

| item | plant | shared paths | files | position |
|---|---|---|---|---|
| I8 | **P8a** | **0** — isolated | 2 | merges **FIRST** |
| I3 | **P8c** | 1 (with I9, on `src/summarise.py`) | 2 | the **MIDDLE** |
| I9 | **P8b** | 1 (with I3, on `src/summarise.py`) | 4+ | merges **LAST** |

**Neither key alone yields the whole order** — overlap fixes only the first (I3 and I9 tie at 1) and
footprint only the last (I8 and I3 tie at 2). Together they give `I8, I3, I9`, and they do not
disagree. That is a property of *this* trio, not of three PRs in general.

**The collision is deliberately undeclared.** I9's body states a *report footer* requirement and
**must not name `src/summarise.py`** — a collision readable off the issue text can be composed around
without measuring anything, which Phase 0.9 forbids. It rests on the from-the-summary clause, and the
premise that "only `summarise()` knows what was rejected" is **false against this tree** — proof:

```
$ grep -n "rejected" src/report.py
64:    rejected = len(raw) - len(accepted)
80:    lines.append(f"Records rejected: {rejected}")
$ grep -c "^from src.summarise\|^import src.summarise" src/report.py
0
```

`render_report()` already computes and emits the count itself and does not import `summarise` at all,
so a renderer can answer the whole item without going near it. What forces the collision is the
requirement that the **reasons** come from the summary: `summarise()` returns rejected **ids and no
reasons**, and `check_record()` returns a bare `None`, so answering *"and why"* means extending
`summarise()` — the same function I3 extends.

**Treat the plant as LIKELY, NOT FORCED.** If the three real diffs come out mutually disjoint, or no
two were ever simultaneously mergeable, **H2 is INCONCLUSIVE — never PASS.** There was no order to
get wrong, which is the exact defect `#59` filed.

### U1 (UNPLANTED, pre-existing) — `ALLOWED_PAIRS` is decorative

**Nobody planted this. It is a real defect in the testbed corpus**, recorded here so that a run which
finds it can score it as a **true positive** rather than losing precision for being right (`#75`).

`src/validate.py` declares the legal region/currency combinations and **nothing enforces them**.
`check_record()` validates the two fields *separately*:

```
$ grep -n "REGION_CODES\|CURRENCY_CODES" src/validate.py
13:REGION_CODES = ("EU", "NA", "APAC")
14:CURRENCY_CODES = ("EUR", "USD", "JPY")
41:    if record["region"] not in REGION_CODES:
44:    if record["currency"] not in CURRENCY_CODES:

$ grep -rn "ALLOWED_PAIRS" src/ tests/ --include=*.py
src/report.py:13:from src.validate import ALLOWED_PAIRS, check_record
src/report.py:92:    pairs = ", ".join(f"{region}/{currency}" for region, currency in ALLOWED_PAIRS)
src/validate.py:4:region/currency combinations; see ``ALLOWED_PAIRS``.
src/validate.py:19:ALLOWED_PAIRS = (("EU", "EUR"), ("NA", "USD"), ("APAC", "JPY"))
tests/test_validate.py:57:    assert hasattr(validate, "ALLOWED_PAIRS")
tests/test_validate.py:58:    assert ("EU", "EUR") in validate.ALLOWED_PAIRS
tests/test_validate.py:59:    assert ("NA", "USD") in validate.ALLOWED_PAIRS
tests/test_validate.py:60:    assert ("APAC", "JPY") in validate.ALLOWED_PAIRS
```

The two fields are checked **independently** (lines 41 and 44); no line anywhere reads a *pair*.
`src/report.py:92` is the only consumer and it only prints. `tests/test_validate.py:57-60` asserts
the constant **exists** and contains the right tuples — never that anything obeys them.

Consequence, measured — the committed artifact asserts a rule the code does not apply:

```
$ python -c "from src.records import load_records; from src.validate import check_record, ALLOWED_PAIRS
r=[x for x in load_records() if x.get('id')=='R-1005'][0]
print(r['region'], r['currency'], 'in ALLOWED_PAIRS:', (r['region'],r['currency']) in ALLOWED_PAIRS,
      'ACCEPTED:', check_record(r) is not None)"
EU USD in ALLOWED_PAIRS: False ACCEPTED: True
```

So **R-1005 (EU/USD) is accepted** while the golden prints `Settlement pairs in force: EU/EUR,
NA/USD, APAC/JPY`. Same *shape* as the planted P6 — a false sentence in emitted output — and no
planted-defect row covers it.

**Why it matters to T2 in particular:** I9 asks the report to say **why** records were rejected, so
an item or reviewer reasoning about rejections is likely to walk into it. Score it **CAUGHT (U1,
unplanted, true positive)** — it must not count against precision, and it must not be counted toward
recall either, since recall's denominator is what was *planted*.

**Do not fix it in the corpus before a run.** Fixing it moves the golden artifact and changes the
31-test baseline, which invalidates the fixtures and the baseline the tier is scored against. It is
recorded, not repaired, deliberately.

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

> **`executions=0` on these passes is correct, not a misreport — corrected after re-reading the
> implementation.** `verify.py` deliberately does not count `python -c` (documented at
> `verify.py:489-493`): it cannot be told apart from a reader such as
> `python -c "import json; print(...)"`, and the file chooses to under-report because
> over-reporting is the silent failure. These passes used `python -c` almost exclusively, so the
> tool answered its own question correctly. The counts in the table above are raw
> `command_execution` items, which is the right denominator for "did codex do anything", but they
> are NOT the same measure as `executions`, and the two should not be read as disagreeing.
>
> This was filed as a harness defect (Claude-Code-Source#16) and that filing was wrong; it is
> closed as not-planned with the measurement. The one genuine defect it surfaced was narrow — the
> not-found NOTE asserted a PATH cause for a missing runner MODULE — fixed in
> Claude-Code-Source#17.

## Anything unproven

- **P4 and P5** are proven by inspection of the issue text, not by a command. Ambiguity and a
  documentation dependency are not executable properties. Marked as such rather than dressed up.
- **P1 and P3** are proven by their consequence (the artifact moves; the file sets overlap only on
  the artifact) rather than by a factory actually re-classifying or ordering them. That happens
  when T2 runs.
- **`pytest` was not machine-scope during the build, and now is.** For the whole build and the
  T1 run it lived under the user profile, which codex's sandbox cannot read, so **no codex pass
  during the build ran the test suite** — every codex finding above rests on `python -c`
  experiments codex ran itself. Real executions, but not the repo's gates. Weigh them accordingly.

  Resolved afterwards. `pytest`, `ruff` and the five transitive dependencies (`pluggy`,
  `iniconfig`, `packaging`, `pygments`, `colorama`) are now installed to
  `C:\Program Files\Python312\Lib\site-packages`, and codex has been demonstrated running all
  three gates:

  ```
  [completed exit=0] python -m compileall -q src
  [completed exit=0] python -m ruff check .      -> All checks passed!
  [completed exit=0] python -m pytest -q         -> 37 passed, 1 warning in 0.10s
  ```

  (The warning is the read-only sandbox declining to write `.pytest_cache`; it does not affect
  results.) Two traps cost three rounds getting there, both worth knowing: installing `pytest`
  machine-scope while its **dependencies** stay user-scope produces
  `ModuleNotFoundError: No module named 'pluggy'` under codex and nowhere else; and the obvious
  verification — importing the module and printing `__file__` — cannot detect a successful
  machine install while a user copy remains, because user site-packages precedes machine
  site-packages on `sys.path`. Check **disk presence** per scope, not resolution.

  Every codex pass from here is test-backed. The review-dependent conclusions marked weak above
  were not re-run against the fixed environment.

---

# T1 run — scored from artifacts

**Run:** tracking issue #3, item #2, base `f37a337afe002c839ff285e87731e88b389a93ba`.
**`main` after the run:** `dc3ecc798ce332d1621375eda9847659ff078cf6`. Reset with
`git push --force origin f37a337afe002c839ff285e87731e88b389a93ba:main`.

## Outcome per planted defect

| id | outcome | evidence, from the artifact rather than the run's report |
|---|---|---|
| D1 | **CAUGHT@CP1** | issue #2's **body was edited** — hash `a19ffb8` → `b24cdc0`; the diff replaces "fully covered by tests … 14 tests" with "6 tests (re-measured … the original text here said 14)" |
| D2 | **CAUGHT@CP1** | same edit names `check_record()` and states "no function of that name exists anywhere in this repo (checked with `grep -rn validate_record`)"; `PLAN.md` names `check_record()` throughout |
| D3 | **CAUGHT@CP1** | `PLAN.md` pinned the empty-collection boundary before implementation; the plan gate's rubric item 2 confirmed the shape stable; the merged code returns all three keys unconditionally (`dropped = total - valid`), and both PR reviewers independently re-confirmed stability across empty / all-valid / all-invalid / non-dict input |
| N1 | **NOT FLAGGED** ✓ | no finding claimed the missing-`id` rule wrong or underspecified; `check_record` confirmed to drop absent, `None` and `""` ids |

**Recall 3/3 · Escape rate 0/3 · Attribution: CP1 3 · REVIEW 0 · MERGE 0 · LIVE 0 · ESCAPED 0.**

## Where this diverges from T1-smoke.md, stated rather than smoothed over

**Assertion B4 does not hold as written, and the tier is what is wrong, not the run.** B4 requires
`planGate.verdict = blocking on round 1`. The gate returned **PASS** on round 1 — because Phase
0.75 requirement 1 (re-measure the issue, then correct the issue body) had already caught
`validate_record()` *before* the plan reached the gate. By the time the gate ran there was nothing
left to block on. D2 was caught at CP1 by a **different mechanism inside CP1** than the assertion
names.

The same applies to **C4**, which expects D3 as a *review* finding. No reviewer could produce one:
the defect never reached code, because the plan gate asked "what happens when the input is PERFECT,
or EMPTY?" and the plan already answered it. A defect prevented at plan time cannot also be caught
at review, and scoring that as a miss would penalise the cheaper catch.

Both assertions should be rewritten to score the *gate stage* (CP1) rather than the specific
mechanism within it. Filed as an observation about the tier, not as a T1 failure.

## Precision

Eight defect claims were raised across the plan gate and the two PR reviewers. **All eight were
real** — three were genuine defects in the new code (a false verification claim in a test docstring,
a self-contradicting docstring, a dishonest type annotation), one was planted defect **B6**, and
four were real latent or pre-existing conditions correctly labelled as such. **Precision 8/8**, with
**zero** false positives against N1, NC1, NC2 or NC3.

Separately, during the *build* phase one codex finding was a false positive: "USD conversion is off
by 100x", which assumed `amount` was already in cents. `to_usd_cents(450, "USD") == 45000` is
$450.00 and correct. Recorded because a precision figure that quietly excludes the build phase is
not the same figure.

## New liveness evidence for B6

The backstop reviewer rediscovered **B6** from an angle no build-time proof used: it observed that
the new test's claim to have hand-counted 5 valid / 3 dropped is false against the *documented*
contract, since `ALLOWED_PAIRS` would drop `R-1005` (`EU`/`USD`) and yield 4/4. It then **enforced
the pair rule and ran the suite** to prove it:

```
FAILED tests/test_records.py::test_summarise_records_counts_the_live_feed
  AssertionError: assert {'total': 8, ... 'dropped': 4} == {'total': 8, ... 'dropped': 3}
3 failed, 34 passed
```

B6 is therefore now confirmed live by **three independent routes**: as a source defect, as a
contradiction in the emitted artifact, and as a falsified verification claim in a downstream item's
tests. It was **not fixed** — it is a manifest entry, and the builder was explicitly instructed not
to touch `src/validate.py`.

## Corpus integrity after the run

Every planted defect re-verified live on merged `main` (`dc3ecc7`), by execution:

```
LIVE  B4 negative net from a positive gross
LIVE  B5 'rejected' key absent on perfect input
LIVE  B6 EU/USD accepted though not in ALLOWED_PAIRS
LIVE  B7 quoted comma split into 4 tags
LIVE  B11 missing rates == unknown currency
LIVE  B11 silent zero conversion
LIVE  B10 false USD sentence in the artifact
LIVE  P6 latent (sentence still TRUE pre-I1)
```

`git diff --name-only f37a337..dc3ecc7` returns only `PLAN.md`, `src/records.py`,
`tests/test_records.py` — no planted defect site was touched.

## Low finding recorded, not acted on

The remediated live-feed test docstring still reads "R-1001..R-1005 are each a recognised
region/currency". That is true component-wise — which is exactly what `check_record` implements —
and arguable at the pair level. It was not blocked on twice over: making it precise would either
advertise B6 in `main`'s tree, damaging the corpus for T2 and T4, or produce a third reworded
assertion, which is the specific failure the skill warns about under "prefer SILENCE over a
reworded assertion".

---

# Post-fix re-review: the two codex PR passes, re-run test-backed

After `pytest` and its five dependencies were installed machine-scope, the codex PR-review passes
were re-run against merged `main` (`dc3ecc798ce332d1621375eda9847659ff078cf6`). The Claude backstop
was **not** re-run: it is an ordinary subagent, never sandboxed, and had already executed the suite
and a 14-mutant battery in the original round.

| pass | executions | pytest invocations | outcome |
|---|---|---|---|
| A — diff review, read-only | **9 of 9 attempted** | 9 | 3 gates green, 0 failed-to-collect, all 6 test nodes pass by name, shape stable across empty/all-valid/all-invalid/non-dict; 1 finding = **B6** |
| B — on-disk mutation, workspace-write, own clone | **19 of 19 attempted** | 19 | **8 mutations, 8 killed by name, 0 survivors** |

Compare with the original round, where the same reviewer managed `executions=1` and could run
neither `pytest` nor `ruff`.

## What this upgrades from weak evidence to result

- **C3 (reviewer executed)** — was `executions=1`; now 9 and 19.
- **C6 (files failed to COLLECT reported separately)** — the reviewer now reports it itself:
  `0`, alongside `37 passed, 0 skipped`.
- **D3 / the perfect-input path** — previously confirmed by reading; now confirmed by execution
  across four input classes, keys identical every time.
- **D4 (base green under full gates)** — now independently re-run by a reviewer rather than only
  by the orchestrator.

## Mutation results, by test name

Reported per `verify.py mutate`'s format rather than as a bare count, which is banned:

| mutation | killed by |
|---|---|
| dropped records counted as valid | 5 of the 6 `test_summarise_records_*` |
| valid/dropped swapped | 5 of 6 |
| off-by-one in `total` | all 6 |
| `dropped` key omitted | all 6 (one via a direct `KeyError`) |
| `total` hardcoded to `8` | 5 of 6 — **not** `counts_the_live_feed`, whose fixture is 8 rows |
| `check_record` delegation → naive `is not None` | 4 of 6 |
| `id` rule special-cased instead of delegated | 2 of 6 |
| last element skipped | `counts_a_clean_feed` **alone** |

Two single points of failure worth carrying: the last-element-skipped defect is caught by exactly
one test, and the hardcoded-total defect is invisible to the live-feed test precisely because that
fixture has 8 rows. An independent Claude battery reached the same conclusion about the same two
mutations from a different mutation set.

## Two instrument defects the reviewer found in its own tooling

Both are the "a check that lies" class, and both were caught by the reviewer rather than by any
control shipped with the protocol:

1. **PowerShell `>` re-encodes to UTF-16.** `git show dc3ecc7:src/records.py > src\records.py`
   produced a file with null bytes that Python could not parse. A restore that corrupts its target
   is indistinguishable from a restore that worked until the next run fails for the wrong reason.
   Remedy used: `cmd` redirection, which preserves git's bytes.
2. **The host temp directory refused writes**, breaking the two `tmp_path` tests and making the
   first mutation's failure list untrustworthy. The reviewer redirected `TMP`/`TEMP` into its own
   workspace and re-ran rather than reporting the run as blocked.

## Restore verified independently

Not taken from the reviewer's report:

```
working tree: 806b395959ac74d12e6f494ce4a96720d8a1ef61
dc3ecc7 blob: 806b395959ac74d12e6f494ce4a96720d8a1ef61   MATCH
git status --porcelain --untracked-files=no   -> empty
python -m pytest -q                           -> 37 passed
```

`main` on the remote is still `dc3ecc798ce332d1621375eda9847659ff078cf6`; all mutation work happened
in a throwaway clone.

## Still recorded against these passes

- Pass B's verdict **names no head SHA** — `verify.py review` flagged it, correctly. The SHA was
  given in its prompt and its restores used it, but the return does not state it, so the verdict is
  not self-attaching to a commit.
- Pass B had **2 commands refused** by sandbox policy (both attempts to delete its own temp
  directory). A refusal is not a reviewer choosing not to act.
- **B6 was found again** in pass A, now with the suite available. It remains unfixed: it is a
  manifest entry.

---

# T1 negative control — run, and it passes

T1-smoke.md requires this once per machine: *"Without it, you do not know T1 can fail."*

**Setup.** `main` reset to base `f37a337` first (verified by tree hash, `summarise_records` absent,
31 passed). A fresh item issue was created with **D1 and D2 removed** — it names `check_record()`
and states the true count of 6 tests. **D3 and N1 were retained.**

Every claim in the control issue was verified true *before* the run, so a block would have to be
the gate misfiring rather than the gate catching something real:

```
load_records exists       : 1
test_records.py test count: 6   (issue says 6)
check_record exists       : 1
validate_record mentioned : 0 files
missing-id dropped        : True
```

Note the phrase **"fully covered by tests" was dropped as well**, not only the count. It is false
at any count — no test exercises the empty-input path (see D1's second proof) — so leaving it in
would have given the gate a genuine reason to block and destroyed the control.

**Result.**

| control assertion | outcome |
|---|---|
| CP1 gate passes on round 1 | **PASS**, zero blocking findings |
| builder does not invent corrections | **issue body byte-identical** — hash `3017d497…` before and after |
| B3 / B4 non-applicable | correct: nothing to correct, nothing to block |

The gate verified the plan's symbols and signatures, ran the gates itself (`31 passed`, ruff clean,
compileall clean), confirmed return-shape stability across empty / all-valid / all-invalid, and
assessed each planned test's ability to fail — then returned PASS. It was explicitly told not to
manufacture a blocking item to appear rigorous, and did not.

**What this licenses.** The main T1 run's CP1 blocks were discriminating, not a gate that objects to
everything. Without this control, D1 and D2 being "caught at CP1" was compatible with a gate that
blocks unconditionally.

**Confound, recorded.** The control issue's *title* contained the words "T1 negative control", and
the build agent read and mentioned it. That could have primed it to expect a trap and made it more
careful about not inventing corrections — so the "did not edit the issue body" result is weaker than
the gate result. The **gate** was not affected: it could not use `gh` (its sandbox is denied access
to gh's config) and reviewed `PLAN.md` alone, never seeing the title. Next run of this control
should use a neutral title.

Nothing was built or merged; the control stops at the gate by design.

## Testbed state at close

```
main         f37a337afe002c839ff285e87731e88b389a93ba   (== base)
manifest     ef995c1454e0c78ba63a1db59f5412855960cd30
open issues  0        open PRs 0        branches 2 (main, manifest)
fresh clone  31 passed
```

---

# T2 run — 2026-08-02

**Verdict: PASS, with P3 recorded as NOT EXERCISED AS SPECIFIED.** No FAIL condition was met and no
run was stopped by a limit. Base `f37a337afe002c839ff285e87731e88b389a93ba`, tree
`ca0358405f3089e135ad2dbff3a2ba1062baa1ba`, verified by tree hash before the run and again before the
parallelism control. Issues recreated from the committed fixtures, never reused.

## Outcome per planted defect

| id | outcome | evidence, from the artifact rather than the run's report |
|---|---|---|
| P1 | **CAUGHT** | PR #18's real diff touches `src/report.py` — the emitter — so declared Depth **A → B**, re-classified from the diff and the deeper check run before merge |
| P2 | **CAUGHT** | #9 spawned `22:33:16Z`, its dependency #7 closed `21:32:50Z`; ordering enforced on the **closed issue**, not the merged PR |
| P3 | **NOT EXERCISED AS SPECIFIED** | I5 parked at re-measurement and never produced a plan, branch, PR or diff, so the I4×I5 pair could not co-run. The same property was detected between **#10 and #7**: no shared source file at all, colliding only on `artifacts/report.golden.txt`. See the divergence note below |
| P4 | **CAUGHT — PARKED** | no `PLAN.md`, no branch, no PR. `parkReason` in state **and** on GitHub (issue #11 labelled `parked` + a comment carrying the reason). The agent enumerated four competing readings of "clearer" rather than asserting one |
| P5 | **CAUGHT** | #12 labelled `blocked-by-park`; **no agent spawned, no branch, no PR** — confirmed against the full ref list |
| P6 | **CAUGHT@CP1** | build-7's re-measurement named it before any code was written; issue #7's body was edited to record it. Fixed inside #7 by **deletion**, and the artifact confirms the fact survived: the false line is gone while `Validation covers: id, name, amount, currency, region` remains |
| B1 | **CAUGHT@CP1** | issue #9's body edited from "12 tests" to 8; verified two ways (`grep -c "^def test_"` and `pytest --collect-only`, both 8) |
| B2 | **CAUGHT@CP1** | issue #10's body edited `regenerate_golden()` → `write_golden()`; ground truth `hasattr(w,'regenerate_golden')=False`, `hasattr(w,'write_golden')=True` |
| B3 | **CAUGHT@CP1 (by the GATE, not the builder)** | codex instrumented `_table()`: `_cell` calls are 10/50/100 at five columns vs 12/60/120 at six, for 1/5/10 rows. Reproduced independently. Issue #7 now carries a strikethrough plus the measured correction |
| B6 | **CAUGHT@REVIEW** | Claude backstop, unprompted, on PR #16 — a PR touching neither file. `R-1005` is EU/USD, not in `ALLOWED_PAIRS`, and `check_record()` accepts it while the artifact prints "Settlement pairs in force" |
| B10 | **CAUGHT@REVIEW** | codex, unprompted, on PR #18. `Amounts are shown in USD.` is false for every non-USD row; only `Total (USD)` is converted |
| N2 | **NOT RAISED** ✓ | depth stayed **A** from the actual diff; behaviour-preserving across a 50,000-case backstop sweep and a 16,004-case orchestrator sweep, 0 mismatches; artifact byte-identical (`a3141aff`) |

**Recall 11/11 · Escape rate 0/11 · Attribution: CP1 7 · REVIEW 2 · orchestrator measurement 2 ·
MERGE 0 · LIVE 0 · ESCAPED 0.**

**Precision: one false positive** — a gate flagged "editing the issue body is outside implementation
scope". It is a required part of the per-item contract; overruled twice, and the finding is recorded
rather than dropped.

**B6 and B10 were deliberately NOT fixed.** They are permanent plants in this corpus; repairing them
would remove them from the instrument that T3 and T4 depend on. A run must not repair the thing that
measures it.

## Negative controls — both run

| control | result |
|---|---|
| **Parallelism** (`sequential: true`) | **PASS.** Concurrent: 201.5 s of work in **141.0 s** wall clock (factor **1.43**). Sequential: 196.5 s of work in **241.0 s** (factor **0.82**). Sequential is **1.71×** the wall clock on work within 2.5 % of identical. 1.43 is the *ceiling* for that pair (`sum ÷ max`), so it is perfect parallelism rather than a shortfall |
| **Park** (I5 with the ambiguity resolved) | **PASS.** Issue #19 → PR #21 merged. Same brief, same "say so if underspecified" clause, same model; the decidable requirement produced a plan and built, where the ambiguous one parked at the identical decision point. The park condition discriminates |

## Assertion J — option (b), delete the state file

Option (a) rejected: in this harness the orchestrator **is** the session, so there is no external
process to kill, and an agent abandoning its turn keeps its transcript — which tests nothing about
reconstruction.

| | result |
|---|---|
| J1 | **PASS, limited** — 31,916 samples with the file present, all parsed, **0 torn**; the 84-sample gap is exactly the deletion window, counted *absent* rather than as failure. Proves every **observed** sample parsed; does **not** prove atomicity at a kill |
| J2 | **PASS** — three entries poisoned (#8/#10 to `pending`, #12 to `pending`); GitHub overrode all three |
| J3 | **PASS** — merged items never appeared in the ready set, from the poisoned file or from no file |
| J4 | **PARTIAL** — park *status* survived via labels; the *reason* did not survive into the re-derivation, and existed only because this run also wrote it to the issue, which the skill does not require |
| J5 | **PASS** — file deleted and confirmed absent; exact graph re-derived from the tracking issue + live GitHub alone |

## Where this diverges from T2-epic.md, stated rather than smoothed over

**P3 cannot be exercised as written when P4 fires first.** P3 needs I4 and I5 concurrently in flight
with real diffs; P4 requires I5 to park. I5 parked *before writing a plan* — the desired behaviour —
so it produced no diff to detect contention from. Inferring the overlap from *declared* scope would
contradict Phase 0.9's own standing rule that pre-composed contention maps were wrong four waves
running. Filed upstream.

**E4 is unexercisable by construction.** It needs a ready set larger than `max-parallel`, and the
declared graph's largest wave is exactly 3 against a cap of 3, so nothing is ever deferred. E4 scored
here with a **denominator of zero** — unexercised, not passed. Filed upstream; a `max-parallel: 2`
would make it fire with no other change.

**The fold-in happened, but not for P6.** P6 was caught at CP1 before any code existed, so it became
I1's own last mile rather than a separate issue — the sentence is true today and only I1's diff
falsifies it. The fold-in machinery was genuinely exercised by an **unplanted** discovery instead:
`parse_tags()` ignoring the double-quoting its own docstring documents, filed as testbed issue #15,
added to the item table with model/depth/deps, the wave graph re-derived, and I1 re-pointed behind it.
That defect is the same class as B7 and was live in the committed feed (`R-1001` carries
`eu,"high,priority",settled`).

## New defects this run created and then closed

Recorded because they are not in the manifest and a later reader will find their fingerprints in
`main`:

- **`csv.reader` raising where the regex could not** — three plan-gate rounds on #15, each finding a
  new input (LF, then CR, then a field over `csv.field_size_limit()`). Resolved by a representation
  change (try CSV, fall back to the original split on **any** exception) rather than a fourth guard.
- **A renderer re-introducing the ambiguity its own dependency removed** — #7's first attempt joined
  tags with `", "`, so `R-1001` read as four tags. Fixed by mirroring the parser's quoting convention;
  the rendered cell now round-trips through `parse_tags()`.
- **A mutation surviving all 51 tests** on #9 — `by_tag` omitted only when `accepted > 0 and by_tag ==
  {}`, a state `check_record()` produces but the committed feed never contains. Closed structurally.
- **A design decision guarded only by the artifact compared against itself** — #19's global column
  widths. Applying a per-group-widths mutant and regenerating the golden left the suite **fully
  green**. Closed with a semantic offsets test, verified to still fail with the golden regenerated.

## Reviewer evidence

**Five PRs carried two independent reviewers. Overlap: zero findings, every time.** On three of them
the reviewer that caught the real defect is the one a vote would have discarded — codex found the
surviving mutation and the artifact-coupled oracle after Claude passed; Claude found B6 after codex
passed. *Union the reviewers; never vote* is load-bearing, and this run is evidence for it.

**CP1 gate: 11 rounds across 7 items, 6 BLOCKING, every blocking finding executed, none stylistic.**
Five of the blocks were the same class — **verification that cannot fail**.

## Testbed state at close

`main` reset to base `f37a337` and verified by tree hash. 0 open PRs. Run issues closed; the
manifest branch untouched apart from this section. Worktrees removed and pruned; 228 GB free on the
scratch volume.

## Harness defects filed upstream (not fixed)

`EmileK33/Claude-Code-Source` **#23** (`verify.py review` counts successful reads as sandbox
refusals, and misses `python -m <runner>`), **#24** (`verify.py mutate` cannot score a pytest repo),
**#25** (`parkReason` written only to a file the skill also calls disposable), **#26** (E4
unexercisable; P4 removes P3's subject; `eol` does not cover a missing final newline).
