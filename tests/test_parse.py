"""Tests for the packed-column helpers."""

import csv

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


def test_parse_tags_keeps_a_quoted_comma_containing_tag_as_one_tag():
    # The bug this issue is about: a quoted comma must not split its tag.
    assert parse_tags('eu,"high,priority",settled') == ["eu", "high,priority", "settled"]


def test_parse_tags_does_not_raise_on_an_unquoted_embedded_newline():
    # A bare LF turns into a CSV row break, which is flattened into one list --
    # never a throw, and a different (correct) shape than the pre-fix split.
    assert parse_tags("eu,high\npriority,settled") == ["eu", "high", "priority", "settled"]


def test_parse_tags_does_not_raise_on_a_bare_carriage_return():
    # A bare CR crashes csv.reader outright (distinct failure mode from LF);
    # this must fall back rather than propagate, and the fallback's answer is
    # the pre-quoting-aware split's answer for this exact string.
    assert parse_tags("eu,high\rpriority,settled") == ["eu", "high\rpriority", "settled"]


def test_parse_tags_does_not_raise_on_a_field_longer_than_the_csv_field_limit():
    limit = csv.field_size_limit()
    huge = "x" * (limit + 10)
    assert parse_tags(f"eu,{huge},settled") == ["eu", huge, "settled"]


def test_parse_tags_falls_back_to_the_old_split_exactly_when_csv_parsing_raises():
    # Bare CR forces the fallback; this also carries a quoted field, so it
    # pins that the fallback's quote-stripping survived, not just that it ran.
    assert parse_tags('eu,"high",bad\rsettled') == ["eu", "high", "bad\rsettled"]


def test_parse_tags_does_not_raise_on_an_unterminated_quote():
    assert parse_tags('eu,"high,priority,settled') == ["eu", "high,priority,settled"]


def test_parse_tags_handles_a_doubled_quote_as_an_escaped_literal_quote():
    assert parse_tags('eu,"""quoted""",settled') == ["eu", '"quoted"', "settled"]


def test_parse_tags_drops_a_quoted_empty_field():
    # Latent bug fixed in passing: the pre-quoting-aware split's empty-field
    # filter ran on the still-quoted part ('""', truthy) before quote
    # stripping reduced it to "", so an empty tag survived even though the
    # docstring promises empty fields are dropped. Pinned deliberately.
    assert parse_tags('eu,"",settled') == ["eu", "settled"]


def test_parse_tags_pins_the_shape_of_a_malformed_doubled_quote_mid_field_row():
    # No such row exists in data/records.json today; this documents the
    # decision rather than leaving the shape to accident.
    assert parse_tags('a,""b"",c') == ["a", 'b""', "c"]
