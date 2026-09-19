"""Regenerate the committed report artifact.

Run from the repository root::

    python -m tools.write_golden
"""

from __future__ import annotations

from pathlib import Path

from src.report import render_report, validation_coverage_line

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "report.golden.txt"


def write_golden(path: str | Path | None = None) -> Path:
    """Render the report and write it to *path*, returning where it landed.

    The newline is pinned so the artifact is byte-identical on every platform;
    ``tests/test_golden.py`` compares bytes, not lines.
    """
    target = Path(path) if path is not None else GOLDEN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_report())
    return target


def summarise_artifact() -> str:
    """One line describing the committed artifact, for the release notes.

    Historically the report ended with the validation-coverage line, so the
    last line was the one worth quoting. #247 appends a "Rejected records"
    footer after it, and separately, render_report() prints feed-controlled
    text (a record's ``name``/``id``) completely unescaped, so scanning the
    rendered report for this fact -- by position OR by prefix -- is not
    safe: a malicious record could forge a line that looks like the
    genuine one. This calls src.report.validation_coverage_line() directly
    instead, the same single source of truth render_report() itself uses,
    so this never reads rendered (and therefore feed-forgeable) text at all.
    """
    return validation_coverage_line()


if __name__ == "__main__":
    print(write_golden())
