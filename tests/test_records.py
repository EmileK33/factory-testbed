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


def test_load_records_rejects_int_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, 42]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*int"):
        load_records(feed)


def test_load_records_rejects_none_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, None]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*NoneType"):
        load_records(feed)


def test_load_records_rejects_bool_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, True]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*bool"):
        load_records(feed)


def test_load_records_rejects_float_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, 3.14]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*float"):
        load_records(feed)


def test_load_records_rejects_string_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, "hello"]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*str"):
        load_records(feed)


def test_load_records_rejects_nested_pair_list_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, [["k", "v"]]]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*list"):
        load_records(feed)


def test_load_records_rejects_empty_list_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, []]), encoding="utf-8")
    with pytest.raises(ValueError, match="element 1 is not a mapping.*list"):
        load_records(feed)


def test_load_records_error_includes_file_path(tmp_path):
    feed = tmp_path / "myfeeds" / "test.json"
    feed.parent.mkdir(parents=True)
    feed.write_text(json.dumps([42]), encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        load_records(feed)
    assert str(feed) in str(exc_info.value)
    assert "element 0" in str(exc_info.value)
