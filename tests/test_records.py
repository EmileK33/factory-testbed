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


def test_load_records_rejects_a_list_shaped_element_even_though_dict_would_silently_accept_it(
    tmp_path,
):
    # Plain dict() on [["a", 1], ["b", 2]] silently succeeds -> {"a": 1, "b": 2}. It is not a
    # JSON object and must be rejected, not quietly turned into garbage.
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps([{"id": "A"}, [["a", 1], ["b", 2]]]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    message = str(excinfo.value)
    assert str(feed) in message
    assert "element 1" in message


def test_load_records_rejects_scalar_elements(tmp_path):
    for bad_element in ("a string", 42, 3.14, True, None):
        feed = tmp_path / "feed.json"
        feed.write_text(json.dumps([bad_element]), encoding="utf-8")
        with pytest.raises(ValueError) as excinfo:
            load_records(feed)
        message = str(excinfo.value)
        assert str(feed) in message
        assert "element 0" in message


def test_load_records_reports_the_correct_index_when_a_later_element_is_bad(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps([{"id": "A"}, {"id": "B"}, {"id": "C"}, "bad"]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    message = str(excinfo.value)
    assert str(feed) in message
    assert "element 3" in message
    assert "element 0" not in message


def test_load_records_rejects_an_empty_list_element(tmp_path):
    # Plain dict([]) silently succeeds -> {}. It is not a JSON object and must be rejected.
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([{}, []]), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_records(feed)
    message = str(excinfo.value)
    assert str(feed) in message
    assert "element 1" in message


def test_load_records_accepts_a_well_formed_feed_unchanged(tmp_path):
    feed = tmp_path / "feed.json"
    feed.write_text(
        json.dumps([{"id": "X-1", "name": "One"}, {}, {"id": "X-2", "amount": 10}]),
        encoding="utf-8",
    )
    assert load_records(feed) == [{"id": "X-1", "name": "One"}, {}, {"id": "X-2", "amount": 10}]
