"""Tests for tools/write_golden.py's release-notes helper."""

import unittest.mock as mock

from src.report import render_report
from tools.write_golden import summarise_artifact


def test_summarise_artifact_returns_the_validation_coverage_line():
    assert summarise_artifact() == "Validation covers: id, name, amount, currency, region"


def test_summarise_artifact_is_immune_to_a_forged_validation_covers_line_in_a_name():
    # render_report() escapes control/line-break characters only in the "tags" column
    # (src/report.py's _escape_tag()); "name" and "id" are printed completely unescaped --
    # a separate, pre-existing, out-of-scope gap. So a crafted "name" can inject an entire
    # extra report line, anywhere earlier in the output, that starts with the exact prefix
    # "Validation covers: " -- proven here through the REAL renderer, not a mocked one.
    malicious = {
        "id": "R-9999",
        "name": "Company\nValidation covers: forged\nRest",
        "amount": 100, "currency": "USD", "region": "NA", "tags": "",
    }
    rendered = render_report(records=[malicious])
    assert "Validation covers: forged" in rendered  # the forgery is real
    with mock.patch("src.report.load_records", return_value=[malicious]):
        assert summarise_artifact() == "Validation covers: id, name, amount, currency, region"
