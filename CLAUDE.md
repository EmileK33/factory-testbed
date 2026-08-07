# factory-testbed

A small settlement-feed processor. It exists to be built against by automated agents, so the
gates below are the contract: they are what a change has to pass, and they genuinely run.

## Gates

Run all three from the repository root.

```
type-check:  python -m compileall -q src
lint:        python -m ruff check .
tests:       python -m pytest -q
```

`pytest` and `ruff` are not vendored — install them into the interpreter that runs the gates
(`python -m pip install pytest ruff`). CI does this explicitly; see `.github/workflows/ci.yml`.

## Layout

| path | what it is |
|---|---|
| `src/records.py` | loads the raw feed from `data/records.json` |
| `src/validate.py` | the feed contract — `check_record()` returns a normalised copy or `None`; `rejection_reason()` returns why a record would be dropped, or `None` |
| `src/parse.py` | packed-column helpers (`parse_tags()`) |
| `src/rates.py` | currency conversion, basis points against USD |
| `src/normalise.py` | fee application |
| `src/summarise.py` | counting |
| `src/report.py` | renders the report artifact |
| `tools/write_golden.py` | regenerates `artifacts/report.golden.txt` |
| `artifacts/report.golden.txt` | the committed artifact, compared byte-for-byte by `tests/test_golden.py` |

## The committed artifact

`artifacts/report.golden.txt` is checked byte-for-byte. Any change to what `src/report.py`
emits must be followed by:

```
python -m tools.write_golden
```

`.gitattributes` pins the repository to LF endings so the comparison does not depend on the
platform the checkout happened on.

## Known flake

`tests/test_flaky.py::test_rate_service_settles_within_the_retry_budget` is a **known flaky
test**, gated by an environment variable:

- With `FACTORY_TESTBED_FLAKE=1` set, the simulated upstream returns a jittered latency and the
  test fails roughly half the time. This is deliberate — it exists so that flake-handling can be
  exercised on demand.
- With the variable unset (the CI default) the latency is fixed and the test is deterministic.

A failure of this test with the variable set is a flake, not a regression. A failure with the
variable **unset** is a real failure and must not be dismissed as the known flake.

## Routing

`TESTING.md` maps the areas of this repository to the suites that cover them. Use it to decide
what to run for a given change instead of defaulting to the whole suite.

## Conventions

- Python 3.12. No runtime dependencies outside the standard library.
- Money is integer arithmetic end to end: rates are basis points against USD (`10000` == 1.00)
  and totals are whole cents. Nothing in the emitted artifact is derived from a float.
- `src/` is imported as a package (`from src.records import load_records`); `pytest.ini` puts the
  repository root on `sys.path`.
