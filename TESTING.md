# Testing and routing

Which suite covers which area. A change confined to one row should run that row's suite plus
the gates; only a change spanning rows needs the whole suite.

| area | source | suite | notes |
|---|---|---|---|
| feed loading | `src/records.py` | `tests/test_records.py` | reads `data/records.json`; also exercised indirectly by the report suites |
| validation contract | `src/validate.py` | `tests/test_validate.py` | the field contract and the accepted code lists |
| packed columns | `src/parse.py` | `tests/test_parse.py` | called from `check_record()` when normalising a record |
| conversion | `src/rates.py` | `tests/test_pipeline.py` | basis-point arithmetic |
| fees | `src/normalise.py` | `tests/test_pipeline.py` | the negative-gross guard lives here |
| counting | `src/summarise.py` | `tests/test_pipeline.py` | |
| report rendering | `src/report.py` | `tests/test_report.py`, `tests/test_golden.py` | **any change here changes an emitted artifact** |
| the committed artifact | `artifacts/report.golden.txt` | `tests/test_golden.py` | byte-for-byte; regenerate with `python -m tools.write_golden` |
| the known flake | `tests/test_flaky.py` | itself | see CLAUDE.md; gated on `FACTORY_TESTBED_FLAKE` |

## Running a subset

```bash
python -m pytest -q tests/test_records.py
python -m pytest -q tests/test_report.py tests/test_golden.py
```
