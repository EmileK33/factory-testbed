"""Tests for loading the settlement feed."""

import json

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


def _write_feed(tmp_path, rows):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(rows), encoding="utf-8")
    return feed


# Each entry is (shape id, the row itself). `dict()` would raise some
# inconsistent TypeError/ValueError for the first four (int/none/bool/float
# are never iterable, a non-empty string is the wrong length), and would
# *silently* convert the rest into a fabricated record -- e.g. the empty
# string/list vacuously, a list of [key, value] pairs, a list containing a
# two-key dict, and a pair whose first item is unhashable (which, unguarded,
# raises `TypeError: unhashable type` deep inside `dict()`, not the loader's
# own ValueError). The fix rejects every one of them, uniformly, before
# `dict()` is ever called.
NON_DICT_SHAPES = [
    ("int", 42),
    ("none", None),
    ("bool", True),
    ("float", 3.14),
    ("non_empty_string", "bad"),
    ("empty_string", ""),
    ("empty_list", []),
    ("list_of_pairs", [["id", "X"]]),
    ("list_containing_dict", [{"id": 1, "name": 2}]),
    ("pair_with_unhashable_key", [[[], 1]]),
]


@pytest.mark.parametrize("position", ["zero", "nonzero"])
@pytest.mark.parametrize("shape_id,row", NON_DICT_SHAPES, ids=[s[0] for s in NON_DICT_SHAPES])
def test_load_records_rejects_non_dict_row(tmp_path, position, shape_id, row):
    valid = {"id": "V", "name": "Valid"}
    if position == "zero":
        rows = [row]
        index = 0
    else:
        rows = [valid, valid, row]
        index = 2
    feed = _write_feed(tmp_path, rows)

    with pytest.raises(ValueError) as excinfo:
        load_records(feed)

    # Exact-equality on the full message -- not a substring check -- so a
    # mutant that multiplies the index, swaps in a different path, or drops
    # either the path or the index cannot slip through.
    assert str(excinfo.value) == f"{feed}: record at index {index} is not a JSON object"


def test_load_records_returns_exact_copy_of_valid_feed(tmp_path):
    rows = [
        {"id": "X-1", "name": "One", "amount": 10},
        {"id": "X-2", "name": "Two", "amount": 20},
    ]
    feed = _write_feed(tmp_path, rows)
    assert load_records(feed) == rows


def test_load_records_accepts_empty_array(tmp_path):
    feed = _write_feed(tmp_path, [])
    assert load_records(feed) == []
