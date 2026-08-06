"""Tests for the JSON settlement report, independent of the committed golden
artifact -- these catch shape/behavior bugs before (or without) regenerating
artifacts/report.golden.json."""

import json

from src.normalise import apply_fees
from src.rates import to_usd_cents
from src.records import load_records
from src.report_json import render_report_json
from src.validate import check_record


def _accepted():
    return [row for row in (check_record(r) for r in load_records()) if row]


def test_report_json_is_valid_json_ending_with_a_newline():
    text = render_report_json()
    assert text.endswith("\n")
    json.loads(text)  # must not raise


def test_report_json_lists_every_accepted_record_id():
    payload = json.loads(render_report_json())
    ids = {row["id"] for row in payload["records"]}
    assert ids == {row["id"] for row in _accepted()}


def test_report_json_counts_match_the_live_feed():
    payload = json.loads(render_report_json())
    raw = load_records()
    accepted = _accepted()
    assert payload["counts"]["read"] == len(raw)
    assert payload["counts"]["accepted"] == len(accepted)
    assert payload["counts"]["rejected"] == len(raw) - len(accepted)


def test_report_json_names_the_unlabelled_record():
    payload = json.loads(render_report_json())
    assert payload["unlabelled"] == ["Fennel Labs"]


def test_report_json_net_matches_apply_fees_for_every_record():
    payload = json.loads(render_report_json())
    expected_net = {row["id"]: row["net"] for row in apply_fees(_accepted())}
    for row in payload["records"]:
        assert row["net"] == expected_net[row["id"]]


def test_report_json_total_usd_cents_matches_the_derived_sum():
    payload = json.loads(render_report_json())
    expected_total = sum(to_usd_cents(row["amount"], row["currency"]) for row in _accepted())
    assert payload["total_usd_cents"] == expected_total


def test_report_json_with_explicit_empty_records_is_not_the_live_feed():
    payload = json.loads(render_report_json(records=[]))
    assert payload == {
        "records": [],
        "counts": {"read": 0, "accepted": 0, "rejected": 0},
        "unlabelled": [],
        "total_usd_cents": 0,
    }


def test_report_json_does_not_raise_on_non_dict_rows():
    for bad_feed in ([None], ["bad"], [42]):
        payload = json.loads(render_report_json(records=bad_feed))
        assert payload["records"] == []
        assert payload["counts"] == {"read": 1, "accepted": 0, "rejected": 1}
        assert payload["unlabelled"] == []
