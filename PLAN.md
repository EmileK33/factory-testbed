# Plan — item 58: cover untested rules in the validation contract

Add three focused tests to `tests/test_validate.py`. No changes to `src/validate.py`.

## New tests

1. `test_check_record_rejects_a_non_dict_record`
   Asserts `check_record()` returns `None` for non-dict inputs (e.g. a string, a
   list, and `None` itself), pinning the `isinstance(record, dict)` guard.

2. `test_check_record_rejects_an_unknown_region`
   Asserts `check_record({**CLEAN, "region": "LATAM"})` returns `None`, mirroring
   the existing `test_check_record_rejects_an_unknown_currency` but for the
   region code list.

3. `test_check_record_rejects_a_non_integer_amount`
   Asserts `check_record()` returns `None` when `amount` is a non-int value such
   as a float (`500.5`) or a string (`"500"`), pinning the `isinstance(value, int)`
   half of `_is_whole_number` (the bool half is already covered by
   `test_check_record_rejects_a_boolean_amount`).

## Expected result

Test count goes from 31 to 34 passed, 0 skipped. All three gates
(`python -m compileall -q src`, `python -m ruff check .`, `python -m pytest -q`)
must stay clean.
