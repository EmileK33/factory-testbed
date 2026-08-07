"""Tests for the packed-column helpers."""

from src.parse import parse_tags


def test_parse_tags_splits_a_plain_list():
    assert parse_tags("na,settled") == ["na", "settled"]


def test_parse_tags_tolerates_spacing_after_the_separator():
    assert parse_tags("apac, bulk") == ["apac", "bulk"]


def test_parse_tags_keeps_a_quoted_comma_inside_its_tag():
    assert parse_tags('eu,"high,priority",settled') == ["eu", "high,priority", "settled"]


def test_parse_tags_returns_nothing_for_a_blank_column():
    assert parse_tags("") == []
    assert parse_tags(None) == []


def test_parse_tags_passes_an_already_split_column_through():
    assert parse_tags(["already", "a", "list"]) == ["already", "a", "list"]


def test_parse_tags_is_idempotent():
    once = parse_tags("na,settled")
    assert parse_tags(once) == once


def test_parse_tags_does_not_raise_on_a_column_of_an_unusable_type():
    assert parse_tags(17) == []
    assert parse_tags({"na": 1}) == []


def test_parse_tags_does_not_raise_on_a_bare_carriage_return():
    # csv.reader raises csv.Error("new-line character seen in unquoted field")
    # on an unquoted "\r"; parse_tags must still return rather than propagate.
    assert parse_tags("a\rb,c") == []


def test_parse_tags_does_not_raise_on_a_field_past_csvs_size_limit():
    # csv.reader raises csv.Error("field larger than field limit") once a
    # single field exceeds its internal cap; parse_tags must still return
    # rather than propagate.
    assert parse_tags("x" * 200_000) == []


def test_check_record_survives_a_tags_column_that_is_not_a_string():
    from src.validate import check_record

    record = {
        "id": "R-3001",
        "name": "Odd Feed",
        "amount": 1,
        "currency": "USD",
        "region": "NA",
        "tags": ["a", "b"],
    }
    assert check_record(record) is not None


def test_check_record_survives_a_tags_column_that_would_raise_in_csv_reader():
    from src.validate import check_record

    record = {
        "id": "R-3002",
        "name": "Malformed Feed",
        "amount": 1,
        "currency": "USD",
        "region": "NA",
        "tags": "a\rb,c",
    }
    checked = check_record(record)
    assert checked is not None
    assert checked["tags"] == []
