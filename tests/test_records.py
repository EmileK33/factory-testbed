"""Tests for loading the settlement feed."""

import json
from pathlib import Path

import pytest

from src.records import load_records


def test_load_records_returns_a_list_of_dicts():
    records = load_records()
    assert isinstance(records, list)
    assert all(isinstance(record, dict) for record in records)


def test_load_records_preserves_feed_order():
    ids = [record.get("id") for record in load_records()]
    assert ids.index("R-1002") < ids.index("R-1003")
    assert ids.index("R-1001") < ids.index("R-1002")


def test_load_records_reads_an_explicit_path(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps([{"id": "X-1", "name": "One"}, {"id": "X-2", "name": "Two"}]),
        encoding="utf-8",
    )
    assert [record["id"] for record in load_records(feed)] == ["X-1", "X-2"]


def test_load_records_rejects_a_payload_that_is_not_an_array(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps("not a feed"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_returns_independent_copies():
    first = load_records()
    first[0]["name"] = "mutated"
    assert load_records()[0]["name"] != "mutated"


def test_load_records_keeps_the_row_with_no_id():
    assert any("id" not in record for record in load_records())


# --- Regression test for issue #232 (round 5 design) -----------------------------------
#
# Diffs the working feed against a frozen pre-fix reference (tests/fixtures/records_base.json)
# rather than re-deriving an expectation from the working feed's own content, which is what
# every earlier design for this regression test turned out unable to do: a check that is a
# function of the working feed cannot, by construction, tell the correct fix from a plausible
# wrong one that happens to produce the same aggregate, the same id-keyed lookup, or the same
# value under Python's default (type-coercing) equality. See PLAN.md for the full history.

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "records_base.json"
WORKING_FEED = REPO_ROOT / "data" / "records.json"

_ABSENT = object()  # sentinel: JSON key genuinely absent -- distinct from JSON null (None)


def _no_duplicate_keys_hook(pairs):
    """json.loads object_pairs_hook that refuses to silently collapse a duplicate key.

    Default dict-building is last-wins on a duplicate key, so a corrupted feed carrying
    the same key twice in one object parses down to a single, correct-looking value --
    indistinguishable, once parsed, from a clean single-key edit (CP1 gate round 5,
    finding 2). This hook sees the raw pairs before they are collapsed.
    """
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON key {key!r} in one object -- refusing to collapse it")
        seen.add(key)
    return dict(pairs)


def _load_json_no_duplicate_keys(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        pytest.fail(
            f"cannot read {path} -- this test has no reference without it and must not "
            f"be allowed to silently pass: {exc}"
        )
    try:
        return json.loads(text, object_pairs_hook=_no_duplicate_keys_hook)
    except ValueError as exc:
        pytest.fail(f"{path}: {exc}")


def _strict_eq(a, b):
    """Value equality that ALSO requires an exact type match (not subclass-aware).

    Plain `==` treats 720 == 720.0 as True and True == 1 as True (CP1 gate round 5,
    finding 1); this feed's own contract rejects a float or bool amount, so plain `==`
    is not a safe primitive for asserting this feed's content. `type(a) is type(b)` is
    identity, not `isinstance`, so it does not treat `bool` as interchangeable with
    `int` even though `bool` subclasses `int` and `True == 1`.
    """
    return type(a) is type(b) and a == b


def _structural_diff(old, new, path=()):
    """Recursively diff two parsed-JSON values; return [(path, old, new), ...] leaf diffs.

    Containers are walked by position/key, not compared as a whole. A key/index present
    on only one side compares against _ABSENT on the other. Leaf comparison uses
    _strict_eq, not plain ==, so a same-value-different-type substitution (720.0 for
    720) is treated as a difference, not silently accepted.
    """
    if isinstance(old, dict) and isinstance(new, dict):
        entries = []
        for key in sorted(set(old) | set(new)):
            entries.extend(
                _structural_diff(old.get(key, _ABSENT), new.get(key, _ABSENT), path + (key,))
            )
        return entries
    if isinstance(old, list) and isinstance(new, list):
        entries = []
        for i in range(max(len(old), len(new))):
            o = old[i] if i < len(old) else _ABSENT
            n = new[i] if i < len(new) else _ABSENT
            entries.extend(_structural_diff(o, n, path + (i,)))
        return entries
    if old is _ABSENT or new is _ABSENT:
        return [] if old is new else [(path, old, new)]
    if not _strict_eq(old, new):
        return [(path, old, new)]
    return []


def _assert_diff_matches_exactly(diff, expected):
    """Compare a computed diff against a literal, using _strict_eq element-by-element.

    Round 4 ended in `assert diff == expected`: plain tuple equality, which compares
    elements with plain ==, so (path, "n/a", 720.0) == (path, "n/a", 720) is True even
    though 720.0 is the wrong type. This checks path/old/new individually with
    _strict_eq so a same-value-different-type substitution is caught explicitly.
    """
    assert len(diff) == len(expected), f"expected {len(expected)} diff entries, got {diff!r}"
    for (got_path, got_old, got_new), (exp_path, exp_old, exp_new) in zip(diff, expected):
        assert got_path == exp_path, f"{got_path!r} != {exp_path!r}"
        assert _strict_eq(got_old, exp_old), (
            f"{got_path}: old {got_old!r} ({type(got_old).__name__}) != expected "
            f"{exp_old!r} ({type(exp_old).__name__})"
        )
        assert _strict_eq(got_new, exp_new), (
            f"{got_path}: new {got_new!r} ({type(got_new).__name__}) != expected "
            f"{exp_new!r} ({type(exp_new).__name__})"
        )


def test_the_feed_differs_from_the_base_fixture_by_exactly_the_two_intended_edits():
    """Regression test for issue #232, redesigned a fifth time after the CP1 gate found each
    prior step-0 design admitted a plausible-wrong feed. Round 4's version -- a structural
    diff against `git show <base>:data/records.json` -- closed every enumerated feed-shape
    attack (add/remove/duplicate/reorder/compensating-pair/invented-null-id/corrupted-
    unrelated-field) but was itself defeated by three narrower issues: (a) its final
    `assert diff == expected` used plain tuple equality, which treats 720.0 as equal to 720
    and so accepted a float amount the pipeline's own contract rejects; (b) it parsed both
    sides with default JSON parsing, which silently collapses a duplicate object key to its
    last value; (c) it depended on `git show` resolving a commit that this repository's own
    CI checkout (depth 1) does not fetch, so it would fail loudly on every CI run including a
    correct one. This version fixes all three: type-preserving comparison via _strict_eq,
    duplicate-key detection via object_pairs_hook, and a frozen fixture file in place of a
    live git dependency.
    """
    base = _load_json_no_duplicate_keys(BASE_FIXTURE)
    working = _load_json_no_duplicate_keys(WORKING_FEED)
    diff = _structural_diff(base, working)
    _assert_diff_matches_exactly(diff, [
        ((6, "currency"), "GBP", "EUR"),
        ((7, "amount"), "n/a", 720),
    ])


def test__strict_eq_rejects_a_same_value_different_type_substitution():
    """Authoring-time proof for the round-5 fix (requirement: mutate the test and show it
    fails on the wrong input, not just passes on the right one): demonstrates the exact
    failure mode the CP1 gate reproduced is now caught, and names the bool/int trap
    explicitly rather than relying on it silently working out.
    """
    assert 720.0 == 720                  # plain equality: this is Python, not the bug itself
    assert not _strict_eq(720.0, 720)    # the fix: type-preserving equality tells them apart
    assert not _strict_eq(True, 1)       # the bool/int trap the gate named, closed the same way
    assert _strict_eq(720, 720)          # sanity: identical type+value still compares equal


def test__no_duplicate_keys_hook_rejects_a_duplicate_key():
    """Authoring-time proof for the round-5 fix: demonstrates the exact failure mode the CP1
    gate reproduced (a duplicate "currency" key silently collapsing to its last value) is
    now caught at parse time instead of silently accepted.
    """
    duplicate_key_json = '{"id": "R-1007", "currency": "GBP", "currency": "EUR"}'
    with pytest.raises(ValueError, match="duplicate JSON key"):
        json.loads(duplicate_key_json, object_pairs_hook=_no_duplicate_keys_hook)
    clean = json.loads(
        '{"id": "R-1007", "currency": "EUR"}', object_pairs_hook=_no_duplicate_keys_hook
    )
    assert clean == {"id": "R-1007", "currency": "EUR"}
