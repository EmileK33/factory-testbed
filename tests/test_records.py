"""Tests for loading the settlement feed."""

import json

import pytest

from src.records import load_records, summarise_records


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


VALID_RECORD = {
    "id": "R-2001",
    "name": "Test Co",
    "amount": 500,
    "currency": "USD",
    "region": "NA",
    "tags": "na,test",
}


def test_summarise_records_of_an_empty_list():
    # A key that only appears when the collection is non-empty is the
    # specific defect this test exists to catch, so assert the full dict —
    # not just that "dropped" equals 0, but that it is present at all.
    assert summarise_records([]) == {"total": 0, "valid": 0, "dropped": 0}


def test_summarise_records_when_every_record_is_valid():
    records = [VALID_RECORD, {**VALID_RECORD, "id": "R-2002"}]
    assert summarise_records(records) == {"total": 2, "valid": 2, "dropped": 0}


def test_summarise_records_when_every_record_is_invalid():
    records = [{**VALID_RECORD, "currency": "GBP"}, {**VALID_RECORD, "amount": -1}]
    assert summarise_records(records) == {"total": 2, "valid": 0, "dropped": 2}


def test_summarise_records_matches_the_real_feed():
    # These counts are NOT independently derived. tests/test_pipeline.py's
    # equivalent pin routes through the same check_record(), so the two agree
    # by construction and neither is ground truth for the other: if the feed
    # contract changes, both move together and neither notices.
    assert summarise_records(load_records()) == {"total": 8, "valid": 5, "dropped": 3}


def test_summarise_records_counts_a_record_missing_its_id_as_dropped():
    unlabelled = {key: value for key, value in VALID_RECORD.items() if key != "id"}
    assert summarise_records([unlabelled]) == {"total": 1, "valid": 0, "dropped": 1}


def test_summarise_records_counts_a_non_dict_element_as_dropped():
    assert summarise_records([None, "not a record", 42]) == {
        "total": 3,
        "valid": 0,
        "dropped": 3,
    }
