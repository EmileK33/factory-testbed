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


# Tests for non-dict elements (silent cases and errors)


def test_load_records_rejects_empty_list_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([[]]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_empty_string_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([""]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_nested_list_pair(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([["a", "b"]]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_nonempty_string_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(["oops"]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_nested_empty_list(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([[[]]]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_number_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([123]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_null_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([None]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_rejects_boolean_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([True]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_records(feed)


def test_load_records_error_includes_file_path(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(["bad"]), encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        load_records(feed)
    assert str(feed) in str(exc_info.value)


def test_load_records_error_includes_row_index(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps([{"id": "X-1"}, {"id": "X-2"}, "bad"]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc_info:
        load_records(feed)
    assert "row 2" in str(exc_info.value)


def test_load_records_error_includes_element_type(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([123]), encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        load_records(feed)
    assert "int" in str(exc_info.value)


def test_load_records_accepts_empty_dict_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, {}]), encoding="utf-8")
    records = load_records(feed)
    assert len(records) == 2
    assert records[1] == {}
