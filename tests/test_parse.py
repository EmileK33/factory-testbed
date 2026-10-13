"""Tests for the packed-column helpers."""

from src.parse import parse_tags


def test_parse_tags_splits_a_plain_list():
    assert parse_tags("na,settled") == ["na", "settled"]


def test_parse_tags_tolerates_spacing_after_the_separator():
    assert parse_tags("apac, bulk") == ["apac", "bulk"]


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


def test_parse_tags_keeps_a_quoted_comma_as_one_tag():
    assert parse_tags('eu,"high,priority",settled') == ["eu", "high,priority", "settled"]


def test_parse_tags_tolerates_spacing_before_a_quoted_tag():
    assert parse_tags('a, "b,c" ,d') == ["a", "b,c", "d"]


def test_parse_tags_blank_and_whitespace_columns_yield_nothing():
    assert parse_tags("   ") == []
    assert parse_tags(',,a,,') == ["a"]


def test_parse_tags_unterminated_quote_does_not_raise():
    assert parse_tags('a,"b,c') == ["a", "b,c"]


def test_parse_tags_unescapes_a_doubled_quote():
    assert parse_tags('a,"b""c"') == ["a", 'b"c']


def test_parse_tags_does_not_resplit_a_list_or_its_own_output():
    assert parse_tags(["high,priority", "x"]) == ["high,priority", "x"]
    once = parse_tags('eu,"high,priority"')
    assert parse_tags(once) == once


def test_parse_tags_falls_back_to_the_naive_split_when_csv_raises(monkeypatch):
    # Synthetic control: no realistic exporter row reaches csv.Error.
    import csv

    def boom(*args, **kwargs):
        raise csv.Error("synthetic")

    monkeypatch.setattr(csv, "reader", boom)
    assert parse_tags("na, settled") == ["na", "settled"]
