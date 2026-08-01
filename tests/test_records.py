"""Tests for loading the settlement feed."""

import json

import pytest

from src.records import load_records, summarise_records

CLEAN = {
    "id": "R-2001",
    "name": "Test Co",
    "amount": 500,
    "currency": "USD",
    "region": "NA",
    "tags": "na,test",
}


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


def test_summarise_records_counts_a_clean_feed():
    records = [{**CLEAN, "id": f"R-300{i}"} for i in range(3)]
    assert summarise_records(records) == {"total": 3, "valid": 3, "dropped": 0}


def test_summarise_records_counts_the_live_feed():
    """Pinned against the committed ``data/records.json``, hand-counted record by
    record (not derived from ``check_record``, the very contract under test):
    R-1001..R-1005 are each a recognised region/currency with a positive
    integer amount (valid); the unlabelled "Fennel Labs" row has no ``id``,
    "Garnet Rail" has an unrecognised currency (GBP), and "Halcyon Air" has a
    non-numeric amount ("n/a") — three drops.
    """
    result = summarise_records(load_records())
    assert result == {"total": 8, "valid": 5, "dropped": 3}


def test_summarise_records_drops_a_record_with_no_id():
    unlabelled = {key: value for key, value in CLEAN.items() if key != "id"}
    assert summarise_records([unlabelled]) == {"total": 1, "valid": 0, "dropped": 1}


def test_summarise_records_handles_an_empty_list():
    assert summarise_records([]) == {"total": 0, "valid": 0, "dropped": 0}


def test_summarise_records_counts_are_consistent_with_totals():
    records = [
        {**CLEAN, "id": "R-4001"},
        {**CLEAN, "id": "R-4002"},
        {key: value for key, value in CLEAN.items() if key != "id"},
        {**CLEAN, "id": "R-4003", "currency": "GBP"},
        {**CLEAN, "id": "R-4004", "amount": -1},
    ]
    result = summarise_records(records)
    assert result["total"] == len(records)
    assert result["total"] == result["valid"] + result["dropped"]
    assert result == {"total": 5, "valid": 2, "dropped": 3}


def test_summarise_records_drops_non_dict_elements():
    assert summarise_records([None, "not a record"]) == {
        "total": 2,
        "valid": 0,
        "dropped": 2,
    }
