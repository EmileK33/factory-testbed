"""The release-note line quoted from the report."""

from tools.write_golden import summarise_artifact


def test_summarise_artifact_quotes_the_validation_coverage_line():
    assert summarise_artifact() == "Validation covers: id, name, amount, currency, region"
