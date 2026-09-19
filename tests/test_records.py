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


def test_load_records_rejects_non_dict_scalar_at_index_zero(tmp_path):
    feed = _write_feed(tmp_path, [42])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert str(feed) in str(excinfo.value)
    assert "index 0" in str(excinfo.value)


def test_load_records_rejects_non_dict_scalar_at_nonzero_index(tmp_path):
    valid = {"id": "X-1", "name": "One"}
    feed = _write_feed(tmp_path, [valid, valid, None])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert "index 2" in str(excinfo.value)


def test_load_records_rejects_empty_string_element(tmp_path):
    feed = _write_feed(tmp_path, [""])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert "index 0" in str(excinfo.value)


def test_load_records_rejects_empty_list_element(tmp_path):
    valid = {"id": "X-1", "name": "One"}
    feed = _write_feed(tmp_path, [valid, []])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert "index 1" in str(excinfo.value)


def test_load_records_rejects_list_of_pairs_at_index_zero(tmp_path):
    # A row that is a list of [key, value] pairs -- dict() would silently
    # convert this to {"id": "X"}, a plausible-looking fabricated record.
    feed = _write_feed(tmp_path, [[["id", "X"]]])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert str(feed) in str(excinfo.value)
    assert "index 0" in str(excinfo.value)


def test_load_records_rejects_list_of_pairs_at_nonzero_index(tmp_path):
    valid = {"id": "X-1", "name": "One"}
    feed = _write_feed(tmp_path, [valid, valid, [["id", "X"]]])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert "index 2" in str(excinfo.value)


def test_load_records_rejects_list_containing_dict_at_index_zero(tmp_path):
    # A row that is a list containing one 2-key dict -- dict() would
    # silently convert this using the dict's own keys as a (key, value) pair.
    feed = _write_feed(tmp_path, [[{"id": 1, "name": 2}]])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert str(feed) in str(excinfo.value)
    assert "index 0" in str(excinfo.value)


def test_load_records_rejects_list_containing_dict_at_nonzero_index(tmp_path):
    valid = {"id": "X-1", "name": "One"}
    feed = _write_feed(tmp_path, [valid, [{"id": 1, "name": 2}]])
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    assert "index 1" in str(excinfo.value)


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
