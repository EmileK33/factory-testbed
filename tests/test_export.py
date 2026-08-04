"""Tests for the CSV export/import round trip (src/export_csv.py, src/import_csv.py)."""

from pathlib import Path

import pytest

from src.export_csv import render_export
from src.import_csv import parse_export
from src.records import load_records
from src.validate import check_record

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "export.golden.csv"

ACCEPTED_LIVE_RECORDS = [
    checked for checked in (check_record(row) for row in load_records()) if checked
]


def _base_row(**overrides: object) -> dict:
    """A fully-keyed, otherwise-valid hand-built row, with the given fields overridden."""
    row = {
        "id": "R-9000",
        "name": "Scratch Co",
        "region": "EU",
        "amount": 1,
        "currency": "EUR",
        "tags": ["a"],
    }
    row.update(overrides)
    return row


# --- the committed artifact ------------------------------------------------------------


def test_the_export_golden_artifact_is_committed():
    assert GOLDEN_PATH.is_file(), f"missing artifact: {GOLDEN_PATH}"


def test_export_matches_the_committed_golden_artifact():
    committed = GOLDEN_PATH.read_bytes()
    rendered = render_export().encode("utf-8")
    assert rendered == committed, (
        "rendered export differs from artifacts/export.golden.csv; "
        "regenerate it with `python -m tools.write_export_golden`"
    )


def test_render_export_uses_lf_line_endings_only():
    text = render_export()
    assert text.endswith("\n")
    assert "\r" not in text


# --- the round-trip invariant ------------------------------------------------------------


def test_export_round_trips_the_whole_live_feed():
    assert parse_export(render_export()) == ACCEPTED_LIVE_RECORDS


@pytest.mark.parametrize(
    "record",
    ACCEPTED_LIVE_RECORDS,
    ids=[record["id"] for record in ACCEPTED_LIVE_RECORDS],
)
def test_export_round_trips_each_accepted_live_record(record):
    assert parse_export(render_export([record])) == [record]


# --- render_export(rows) does not validate, and only reads the six-column contract -------


def test_render_export_does_not_validate_rows_it_is_given():
    # currency "GBP" is not in CURRENCY_CODES, so check_record would reject this row --
    # render_export must still export it unchanged, because validation is not its job.
    row = _base_row(id="R-9002", currency="GBP")
    assert check_record(row) is None  # sanity: this row is in fact rejectable
    assert parse_export(render_export([row])) == [row]


def test_render_export_ignores_keys_outside_the_six_column_contract():
    # A raw feed row carries a "status" key that check_record() also never returns; the
    # export's column contract is exactly the six FIELDNAMES (see src/export_csv.py's
    # module docstring), so "status" must not survive the round trip.
    row = _base_row(id="R-9003", status="open")
    expected = {k: v for k, v in row.items() if k != "status"}
    assert parse_export(render_export([row])) == [expected]


# --- the awkward values, each its own named test ------------------------------------------


def test_round_trip_preserves_a_value_containing_the_delimiter():
    row = _base_row(id="R-9010", name="Aster, Holdings")
    assert parse_export(render_export([row])) == [row]


def test_round_trip_preserves_a_value_containing_a_quote():
    row = _base_row(id="R-9011", name='Aster "Prime" Holdings')
    assert parse_export(render_export([row])) == [row]


def test_round_trip_preserves_an_empty_string():
    row = _base_row(id="R-9012", name="")
    result = parse_export(render_export([row]))
    assert result == [row]
    assert result[0]["name"] == ""


def test_round_trip_preserves_none():
    row = _base_row(id="R-9013", name=None)
    result = parse_export(render_export([row]))
    assert result == [row]
    assert result[0]["name"] is None


def test_round_trip_preserves_an_empty_tags_list():
    row = _base_row(id="R-9014", tags=[])
    result = parse_export(render_export([row]))
    assert result == [row]
    assert result[0]["tags"] == []


def test_round_trip_preserves_a_multi_element_tags_list_with_an_embedded_comma():
    # Measured against the live feed while planning this item: no live-feed tag actually
    # contains a comma (src.parse.parse_tags splits on every comma regardless of quoting),
    # so this case is hand-built rather than sourced from data/records.json.
    row = _base_row(id="R-9015", tags=["north,south", "priority", "settled"])
    result = parse_export(render_export([row]))
    assert result == [row]
    assert result[0]["tags"] == ["north,south", "priority", "settled"]


def test_none_and_empty_string_do_not_collapse_together():
    none_row = _base_row(id="R-9016", name=None)
    empty_row = _base_row(id="R-9017", name="")
    decoded_none = parse_export(render_export([none_row]))[0]
    decoded_empty = parse_export(render_export([empty_row]))[0]
    assert decoded_none["name"] is None
    assert decoded_empty["name"] == ""
    assert decoded_none["name"] != decoded_empty["name"]


def test_empty_string_and_empty_list_do_not_collapse_together():
    empty_string_row = _base_row(id="R-9018", tags="")
    empty_list_row = _base_row(id="R-9019", tags=[])
    decoded_string = parse_export(render_export([empty_string_row]))[0]
    decoded_list = parse_export(render_export([empty_list_row]))[0]
    assert decoded_string["tags"] == ""
    assert decoded_list["tags"] == []
    assert decoded_string["tags"] != decoded_list["tags"]


# --- malformed-input guards (folded in from the CP1 plan gate's LOW findings) -------------


def test_parse_export_skips_a_trailing_blank_line():
    text = render_export([_base_row(id="R-9020")]) + "\n"
    assert parse_export(text) == [_base_row(id="R-9020")]


def test_parse_export_raises_on_a_row_with_the_wrong_column_count():
    text = render_export([_base_row(id="R-9021")])
    header, data_line = text.splitlines()
    truncated = header + "\n" + data_line.rsplit(",", 1)[0] + "\n"
    with pytest.raises(ValueError, match="expected 6 columns"):
        parse_export(truncated)


def test_render_export_raises_a_clear_error_for_a_non_serialisable_value():
    row = _base_row(id="R-9022", tags={"not", "json", "serialisable"})
    with pytest.raises(TypeError, match="export column 'tags'"):
        render_export([row])
