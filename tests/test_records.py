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


# Every non-object element shape: the ones that raised a TypeError or ValueError from dict(),
# and the ones dict() silently turned into a mapping.
BAD_ELEMENTS = [
    pytest.param("null", id="null"),
    pytest.param("5", id="number"),
    pytest.param("1.5", id="float"),
    pytest.param("true", id="boolean"),
    pytest.param('"ab"', id="string-two-chars"),
    pytest.param("[[1, 2, 3]]", id="triple-in-array"),
    pytest.param("[1, 2]", id="array-of-ints"),
    pytest.param("[null]", id="array-of-null"),
    pytest.param('[["x"], 1]', id="unhashable-key"),
    pytest.param('""', id="silent-empty-string"),
    pytest.param("[]", id="silent-empty-array"),
    pytest.param('[["a", 1]]', id="silent-pair"),
    pytest.param("[[1, 2]]", id="silent-int-key-pair"),
    pytest.param('[["a", "b"], ["c", "d"]]', id="silent-two-pairs"),
]


@pytest.mark.parametrize("element", BAD_ELEMENTS)
def test_load_records_names_the_file_and_index_of_a_non_object_element(tmp_path, element):
    feed = tmp_path / "feed.json"
    feed.write_text('[{"id": "X-1"}, ' + element + "]", encoding="utf-8")
    with pytest.raises(ValueError) as info:
        load_records(feed)
    message = str(info.value)
    assert str(feed) in message
    assert "element at index 1 (0-based) is not a JSON object" in message


def test_load_records_reports_the_index_of_the_offending_element_not_the_first(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text('[{"id": "X-1"}, {"id": "X-2"}, 5]', encoding="utf-8")
    with pytest.raises(ValueError) as info:
        load_records(feed)
    message = str(info.value)
    assert str(feed) in message
    assert "element at index 2 (0-based) is not a JSON object" in message


def test_load_records_reports_a_bad_element_in_the_middle_of_the_feed(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text('[{"id": "A"}, null, {"id": "B"}]', encoding="utf-8")
    with pytest.raises(ValueError) as info:
        load_records(feed)
    assert "element at index 1 (0-based) is not a JSON object" in str(info.value)


def test_load_records_reports_the_first_of_two_bad_elements(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text('[{"id": "A"}, 5, {"id": "B"}, null]', encoding="utf-8")
    with pytest.raises(ValueError) as info:
        load_records(feed)
    message = str(info.value)
    assert "element at index 1 (0-based) is not a JSON object" in message
    assert "index 3" not in message


def test_load_records_names_the_resolved_path_when_called_with_the_default(tmp_path, monkeypatch):
    import src.records as records_module

    feed = tmp_path / "default-feed.json"
    feed.write_text('[{"id": "A"}, 5]', encoding="utf-8")
    monkeypatch.setattr(records_module, "DATA_PATH", feed)
    with pytest.raises(ValueError) as info:
        load_records()
    message = str(info.value)
    assert str(feed) in message
    assert "None" not in message


@pytest.mark.parametrize(
    ("element", "kind"),
    [
        pytest.param("null", "null", id="null"),
        pytest.param("true", "boolean", id="boolean"),
        pytest.param("5", "number", id="number"),
        pytest.param("1.5", "number", id="float"),
        pytest.param('"ab"', "string", id="string"),
        pytest.param("[1, 2]", "array", id="array"),
    ],
)
def test_load_records_names_the_json_kind_of_the_offending_element(tmp_path, element, kind):
    feed = tmp_path / "feed.json"
    feed.write_text('[{"id": "X-1"}, ' + element + "]", encoding="utf-8")
    with pytest.raises(ValueError) as info:
        load_records(feed)
    assert f"(found {kind})" in str(info.value)


def test_load_records_accepts_object_elements_including_an_empty_object(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text('[{"id": "X-1", "tags": ["a", 1]}, {}]', encoding="utf-8")
    assert load_records(feed) == [{"id": "X-1", "tags": ["a", 1]}, {}]


def test_load_records_accepts_an_empty_array(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text("[]", encoding="utf-8")
    assert load_records(feed) == []
