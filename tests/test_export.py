"""Tests for the CSV export/import round trip (src/export_csv.py, src/import_csv.py)."""

from pathlib import Path

import pytest

from src.export_csv import FIELDNAMES, render_export
from src.import_csv import EXPECTED_FIELDNAMES, parse_export
from src.records import load_records
from src.validate import check_record
from tools.write_export_golden import GOLDEN_PATH as TOOL_GOLDEN_PATH
from tools.write_export_golden import write_export_golden

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


# --- type preservation, not just dict equality ---------------------------------------------
#
# `==` alone does not pin type: 1200 == 1200.0 and 1 == True in Python, so a decoder that
# quietly widened int -> float, or collapsed 1 -> True, would pass every round-trip test
# above without being noticed. These assert the concrete type, not just equality.


def test_round_trip_preserves_the_amount_as_an_int_not_a_float():
    row = _base_row(id="R-9023", amount=1200)
    result = parse_export(render_export([row]))[0]
    assert type(result["amount"]) is int
    assert result["amount"] == 1200


def test_round_trip_does_not_confuse_an_amount_of_one_with_boolean_true():
    # isinstance(True, int) is True, so an == check alone cannot tell "amount is 1" apart
    # from "amount is True". type() can.
    row = _base_row(id="R-9024", amount=1)
    result = parse_export(render_export([row]))[0]
    assert type(result["amount"]) is int
    assert not isinstance(result["amount"], bool)


def test_round_trip_preserves_tags_as_a_list_not_some_other_sequence():
    row = _base_row(id="R-9025", tags=["a", "b"])
    result = parse_export(render_export([row]))[0]
    assert type(result["tags"]) is list


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


def test_render_export_of_an_explicit_empty_list_does_not_fall_back_to_the_live_feed():
    # render_export([]) is an explicit "export nothing", not "no argument was given" --
    # `if records is None` must tell those apart. Header-only output, zero data rows.
    text = render_export([])
    assert text == ",".join(FIELDNAMES) + "\n"
    assert parse_export(text) == []


def test_parse_export_of_empty_text_returns_no_records():
    assert parse_export("") == []


def test_parse_export_raises_a_clear_error_for_a_corrupt_cell():
    # Hand-built, not produced by render_export: the "id" cell's wire text ("not-json") is
    # not valid JSON, unlike anything render_export would ever emit.
    text = 'id,name,region,amount,currency,tags\nnot-json,"x","x",1,"x",[]\n'
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_export(text)


def test_parse_export_rejects_a_header_that_does_not_match_the_six_column_contract():
    text = "wrong,name,region,amount,currency,tags\n"
    with pytest.raises(ValueError, match="does not match the expected columns"):
        parse_export(text)


def test_import_csvs_expected_fieldnames_constant_matches_export_csvs_fieldnames():
    # The two modules deliberately keep separate copies of the six-column contract (see
    # src/import_csv.py's module docstring for why); pin that the copies agree.
    assert EXPECTED_FIELDNAMES == FIELDNAMES


def test_parse_export_skips_a_blank_line_between_data_rows_not_just_a_trailing_one():
    row_a = _base_row(id="R-9027")
    row_b = _base_row(id="R-9028")
    header_a, line_a = render_export([row_a]).splitlines()
    _, line_b = render_export([row_b]).splitlines()
    text = f"{header_a}\n{line_a}\n\n{line_b}\n"
    assert parse_export(text) == [row_a, row_b]


def test_round_trip_preserves_non_ascii_text():
    row = _base_row(id="R-9029", name="Müller Ω 株式会社")
    assert parse_export(render_export([row])) == [row]


# --- tools/write_export_golden.py -----------------------------------------------------------


def test_write_export_golden_default_target_is_the_committed_artifact_path():
    assert TOOL_GOLDEN_PATH == GOLDEN_PATH


def test_write_export_golden_reproduces_the_committed_artifact(tmp_path):
    # A nested, not-yet-existing directory forces write_export_golden's mkdir(parents=True)
    # to actually run; a dropped mkdir would raise FileNotFoundError here.
    target = tmp_path / "nested" / "export.golden.csv"
    written_path = write_export_golden(target)
    assert written_path == target
    assert target.read_bytes() == GOLDEN_PATH.read_bytes()
