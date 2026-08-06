"""The committed JSON artifact must match what the emitter produces, byte for
byte, and it must round-trip losslessly against the text report."""

import json
import re
from pathlib import Path

from src.report import render_report
from src.report_json import render_report_json

GOLDEN_JSON_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "report.golden.json"

# The table renderer (src/report.py:_table) joins justified cells with "  ",
# so any run of 2+ whitespace characters is a column boundary; a single space
# inside a cell (e.g. "Aster Holdings") is not.
_COLUMN_BOUNDARY = re.compile(r"\s{2,}")


def _text_records_by_id(text: str) -> dict[str, dict[str, str]]:
    """Parse the "id name region amount currency" table out of *text*.

    Derived straight from the rendered output -- not from re-running
    check_record()/apply_fees() a second time, which would only prove the
    JSON renderer agrees with itself rather than with what the text report
    actually shows.
    """
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("id"))
    rows: dict[str, dict[str, str]] = {}
    for line in lines[header_index + 2 :]:
        if not line.strip():
            break
        cells = _COLUMN_BOUNDARY.split(line.strip())
        row = dict(zip(("id", "name", "region", "amount", "currency"), cells))
        rows[row["id"]] = row
    return rows


def _text_net_by_id(text: str) -> dict[str, int]:
    """Parse the "id  net" lines out of the "Net after fees" section of *text*."""
    lines = text.splitlines()
    start = lines.index("Net after fees") + 2
    nets: dict[str, int] = {}
    for line in lines[start:]:
        if not line.strip():
            break
        record_id, net = _COLUMN_BOUNDARY.split(line.strip())
        nets[record_id] = int(net)
    return nets


def test_the_golden_json_artifact_is_committed():
    assert GOLDEN_JSON_PATH.is_file(), f"missing artifact: {GOLDEN_JSON_PATH}"


def test_report_json_matches_the_committed_golden_artifact():
    committed = GOLDEN_JSON_PATH.read_bytes()
    rendered = render_report_json().encode("utf-8")
    assert rendered == committed, (
        "rendered JSON report differs from artifacts/report.golden.json; "
        "regenerate it with `python -m tools.write_golden_json`"
    )


def test_the_golden_json_round_trips_every_accepted_record_against_the_text_report():
    """Every accepted record in the committed JSON must carry exactly the
    id/name/region/amount/currency and net-after-fees that the *rendered
    text report* shows for that record. Both sides are derived: the JSON
    side by parsing the committed artifact, the text side by parsing
    render_report()'s actual output -- neither is a hardcoded literal.
    """
    text = render_report()
    text_records = _text_records_by_id(text)
    text_nets = _text_net_by_id(text)

    payload = json.loads(GOLDEN_JSON_PATH.read_bytes())
    json_records = {row["id"]: row for row in payload["records"]}

    assert set(json_records) == set(text_records) == set(text_nets)
    assert json_records  # the fixture feed has at least one accepted record

    for record_id, text_row in text_records.items():
        json_row = json_records[record_id]
        assert json_row["name"] == text_row["name"]
        assert json_row["region"] == text_row["region"]
        assert str(json_row["amount"]) == text_row["amount"]
        assert json_row["currency"] == text_row["currency"]
        assert json_row["net"] == text_nets[record_id]
