"""Tests for the per-tag counts in ``summarise()``."""

import csv
import json
from collections import Counter
from pathlib import Path

from src.records import load_records
from src.summarise import summarise
from src.validate import check_record

FEED = Path(__file__).resolve().parent.parent / "data" / "records.json"


def _record(**changes):
    base = {
        "id": "R-9",
        "name": "N",
        "amount": 1,
        "currency": "USD",
        "region": "NA",
        "tags": "na",
    }
    base.update(changes)
    return base


def test_by_tag_matches_the_raw_feed():
    # Held-out: which records are accepted comes from the existing validator,
    # but every tag is read from the RAW feed through csv, not src.parse.
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    expected = Counter()
    accepted_ids = set()
    for raw in feed:
        if check_record(raw) is None:
            continue
        accepted_ids.add(raw["id"])
        row = next(csv.reader([raw["tags"]], skipinitialspace=True))
        expected.update(set(tag.strip() for tag in row if tag.strip()))

    counts = summarise(load_records())
    assert accepted_ids, "no accepted record examined"
    assert len(accepted_ids) < len(feed), "no rejected record in the feed"
    assert expected, "no tag examined"
    assert counts["by_tag"] == dict(expected)
    assert counts["accepted"] == len(accepted_ids)


def test_by_tag_keeps_a_quoted_comma_tag_whole():
    counts = summarise([_record(tags='eu,"high,priority",settled')])
    assert counts["by_tag"] == {"eu": 1, "high,priority": 1, "settled": 1}


def test_by_tag_keeps_the_case_check_record_returns():
    # Keys are the tags exactly as check_record() returns them, so the counts
    # agree with the report's tags column: no case-folding.
    record = _record(tags="EU,eu,settled")
    assert check_record(record)["tags"] == ["EU", "eu", "settled"]
    counts = summarise([record])
    assert counts["by_tag"] == {"EU": 1, "eu": 1, "settled": 1}


def test_by_tag_counts_a_repeated_tag_once_per_record():
    counts = summarise([_record(id="A", tags="a,a, a"), _record(id="B", tags="a,b")])
    assert counts["by_tag"] == {"a": 2, "b": 1}


def test_by_tag_is_an_empty_mapping_when_nothing_is_accepted():
    assert summarise([])["by_tag"] == {}
    assert summarise([_record(amount="n/a")])["by_tag"] == {}
    for tags in ("", None, "  ", [], 5):
        counts = summarise([_record(tags=tags)])
        assert counts["accepted"] == 1
        assert counts["by_tag"] == {}
    missing = _record()
    del missing["tags"]
    assert summarise([missing])["by_tag"] == {}


def test_by_tag_ignores_rejected_records():
    counts = summarise(
        [_record(id="A", tags="a"), _record(id="B", tags="b", currency="GBP"), _record(tags="c", id="")]
    )
    assert counts["by_tag"] == {"a": 1}
    assert counts["rejected"] == ["B", ""]


def test_by_tag_counts_list_and_tuple_shaped_tags():
    counts = summarise(
        [
            _record(id="A", tags=["a", "b"]),
            _record(id="B", tags=("a", "b")),
            _record(id="C", tags=["a", None, "", " c "]),
        ]
    )
    assert counts["by_tag"] == {"a": 3, "b": 2, "c": 1}
    assert counts["accepted"] == 3


def test_by_tag_leaves_the_other_counts_alone():
    counts = summarise([_record(id="A"), _record(id="B", amount="n/a")])
    assert counts["total"] == 2
    assert counts["accepted"] == 1
    assert counts["rejected"] == ["B"]
