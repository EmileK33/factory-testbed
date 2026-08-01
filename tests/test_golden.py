"""The committed artifact must match what the emitter produces, byte for byte."""

from pathlib import Path

from src.report import render_report

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "report.golden.txt"


def test_the_golden_artifact_is_committed():
    assert GOLDEN_PATH.is_file(), f"missing artifact: {GOLDEN_PATH}"


def test_report_matches_the_committed_golden_artifact():
    committed = GOLDEN_PATH.read_bytes()
    rendered = render_report().encode("utf-8")
    assert rendered == committed, (
        "rendered report differs from artifacts/report.golden.txt; "
        "regenerate it with `python -m tools.write_golden`"
    )
