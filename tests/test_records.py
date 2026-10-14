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


BAD_ELEMENTS = [
    pytest.param(7, id="int"),
    pytest.param(1.5, id="float"),
    pytest.param(True, id="bool"),
    pytest.param(None, id="null"),
    pytest.param("ab", id="str-ab"),
    pytest.param("", id="str-empty"),
    pytest.param([], id="list-empty"),
    pytest.param(["ab"], id="list-ab"),
    pytest.param([["a", 1]], id="list-pairs"),
    pytest.param([1, 2, 3], id="list-three"),
]


@pytest.mark.parametrize("bad", BAD_ELEMENTS)
def test_load_records_names_the_file_and_index_of_a_non_object_element(tmp_path, bad):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, bad]), encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_records(feed)
    assert str(caught.value) == (
        f"{feed}: element at index 1 must be a JSON object, got {type(bad).__name__}"
    )


def test_load_records_names_index_zero_for_a_bad_first_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(["ab", {"id": "X-1"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="element at index 0 must be a JSON object, got str"):
        load_records(feed)


def test_load_records_accepts_an_empty_object_element(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{}]), encoding="utf-8")
    assert load_records(feed) == [{}]


def test_load_records_accepts_an_empty_feed(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([]), encoding="utf-8")
    assert load_records(feed) == []
