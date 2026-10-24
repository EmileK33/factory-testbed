"""Tests for the packed-column helpers."""

import pytest

from src.parse import parse_tags

# Every whitespace character str.split() recognises; the count guards the loop below
# against examining nothing.
WHITESPACE = [chr(c) for c in range(0x110000) if not chr(c).split()]

STRING_CASES = [
    ("na,settled", ["na", "settled"]),
    ("apac, bulk", ["apac", "bulk"]),
    ('eu,"high,priority",settled', ["eu", "high,priority", "settled"]),
    ('eu, "high,priority", settled', ["eu", "high,priority", "settled"]),
    ('"say ""hi"""', ['say "hi"']),
    ('"a,b"', ["a,b"]),
    ('"a,b",c', ["a,b", "c"]),
    ('c,"a,b"', ["c", "a,b"]),
    ("a,,b,", ["a", "b"]),
    (",", []),
    ('""', []),
    ('"",a', ["a"]),
    ("", []),
    ("   ", []),
    ("\n", []),
    ("a\nb,c", ["a b", "c"]),
    ("a\r\nb,c", ["a b", "c"]),
    ('eu,"high,\npriority",settled', ["eu", "high, priority", "settled"]),
    ("na,settled\n", ["na", "settled"]),
    ("na,\nsettled", ["na", "settled"]),
    ('eu,"high,priority', ["eu", "high,priority"]),
    ('ab"c,d', ['ab"c', "d"]),
    ('"ab"c,d', ["abc", "d"]),
    ('"a" ,b', ["a", "b"]),
    ('" a ",b', ["a", "b"]),
    ("high   priority,x", ["high priority", "x"]),
    ('"high \t priority,x",y', ["high priority,x", "y"]),
    ("a\x00b,c", ["a\x00b", "c"]),
    ("it's,'fine,x'", ["it's", "'fine", "x'"]),
    ("zzz,eu,Not A Tag", ["zzz", "eu", "Not A Tag"]),
]

SEQUENCE_CASES = [
    (["already", "a", "list"], ["already", "a", "list"]),
    (["a", None, "", "  ", "b"], ["a", "b"]),
    (("a b", "c"), ["a b", "c"]),
    (["high,priority", "x"], ["high,priority", "x"]),
    (["a b", " x\n", "p\t\tq"], ["a b", "x", "p q"]),
    ([5, True], ["5", "True"]),
    ([], []),
    ([None], []),
]


@pytest.mark.parametrize(("raw", "expected"), STRING_CASES)
def test_parse_tags_string_input_space(raw, expected):
    got = parse_tags(raw)
    assert got == expected
    assert parse_tags(got) == got


@pytest.mark.parametrize(("raw", "expected"), SEQUENCE_CASES)
def test_parse_tags_sequence_input_space(raw, expected):
    got = parse_tags(raw)
    assert got == expected
    assert parse_tags(got) == got


def test_parse_tags_keeps_the_quoted_comma_tag_of_r_1001_whole():
    assert parse_tags('eu,"high,priority",settled') == ["eu", "high,priority", "settled"]


def test_parse_tags_oversize_field_is_one_tag_not_a_raise():
    raw = "big," + "x" * 140000
    assert parse_tags(raw) == [raw]


def test_whitespace_set_has_the_expected_denominator():
    assert len(WHITESPACE) == 29


@pytest.mark.parametrize("w", WHITESPACE, ids=lambda w: f"U+{ord(w):04X}")
def test_parse_tags_normalises_every_whitespace_character(w):
    assert parse_tags(f"a{w}b,c") == ["a b", "c"]
    assert parse_tags(f"{w}a{w}") == ["a"]
    assert parse_tags(f'eu,{w}"x{w}y,z"{w},settled') == ["eu", "x y,z", "settled"]
    assert parse_tags(f"a,{w},b") == ["a", "b"]
    assert parse_tags([f"a{w}b", None, "", w, f"{w}c{w}"]) == ["a b", "c"]
    assert parse_tags((f"p{w}q",)) == ["p q"]


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
