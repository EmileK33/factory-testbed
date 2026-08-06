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


def test_parse_tags_does_not_re_split_a_comma_inside_an_already_split_element():
    # Regression guard for the passthrough branch: a comma living inside one
    # element of an already-split sequence must not be treated as a separator.
    assert parse_tags(["eu", "high,priority"]) == ["eu", "high,priority"]


def test_parse_tags_keeps_a_quoted_tag_containing_a_comma_as_one_tag():
    # The bug in issue #87: a tag wrapped in double quotes (the upstream
    # exporter's own contract, per this module's docstring) must survive as a
    # single tag rather than being torn apart at the comma it contains.
    assert parse_tags('eu,"high,priority",settled') == ["eu", "high,priority", "settled"]


def test_parse_tags_ends_quoting_at_the_closing_quote_of_a_field_initial_quote():
    # Intentional behaviour change from the old regex, adjudicated during
    # PLAN.md's round-1 gate ("Case A"): a quote character that OPENS a field
    # (i.e. is the field's first character) is treated as real quoting, per
    # csv's standard reading and the docstring's "wrapped in double quotes"
    # contract - not preserved literally the way the old regex accidentally
    # did via a blind leading/trailing `.strip('"')`.
    assert parse_tags('a,"b"c,d') == ["a", "bc", "d"]


def test_parse_tags_drops_an_explicitly_quoted_empty_tag():
    # Intentional behaviour change from the old regex, adjudicated during
    # PLAN.md's round-1 gate ("Case B"): an explicitly quoted empty field
    # yields no tag, consistent with every other blank value in this function
    # producing no tag rather than a bare empty-string entry.
    assert parse_tags('a,""') == ["a"]


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
