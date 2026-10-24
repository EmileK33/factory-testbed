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


NON_OBJECT_ELEMENTS = [
    pytest.param(5, "number", id="int"),
    pytest.param(None, "null", id="null"),
    pytest.param(True, "boolean", id="bool"),
    pytest.param(1.5, "number", id="float"),
    pytest.param("ab", "string", id="string"),
    pytest.param("", "string", id="empty-string"),
    pytest.param([["a", 1]], "array", id="array"),
    pytest.param([], "array", id="empty-array"),
    pytest.param(["ab"], "array", id="array-of-strings"),
]


@pytest.mark.parametrize("element, kind", NON_OBJECT_ELEMENTS)
def test_load_records_rejects_a_non_object_element(tmp_path, element, kind):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, element]), encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_records(feed)
    assert str(caught.value) == (
        f"{feed}: element at index 1 (counted from 0) is not a JSON object; its JSON type is {kind}"
    )


def test_load_records_rejection_names_the_file(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{"id": "X-1"}, 5]), encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_records(feed)
    assert str(feed) in str(caught.value)


def test_load_records_rejection_names_the_index(tmp_path):
    first_bad = tmp_path / "first.json"
    first_bad.write_text(json.dumps([5, {"id": "X-1"}, None]), encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_records(first_bad)
    assert "index 0" in str(caught.value)

    third_bad = tmp_path / "third.json"
    third_bad.write_text(json.dumps([{"id": "X-1"}, {"id": "X-2"}, None]), encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_records(third_bad)
    assert "index 2" in str(caught.value)


def test_load_records_accepts_well_formed_feed(tmp_path):
    feed = tmp_path / "feed.json"
    rows = [{"id": "X-1", "tags": ["a", "b"], "amount": {"value": 5}}, {}]
    feed.write_text(json.dumps(rows), encoding="utf-8")
    assert load_records(feed) == rows

    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert load_records(empty) == []
