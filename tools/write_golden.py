"""Regenerate the committed report artifact.

Run from the repository root::

    python -m tools.write_golden
"""

from __future__ import annotations

from pathlib import Path

from src.report import render_report

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

    The report ends with the rejection footer, so the line worth quoting is the
    validation-coverage line above it. Nothing downstream re-derives this, so it
    is read as written.
    """
    (line,) = [
        line for line in render_report().splitlines() if line.startswith("Validation covers: ")
    ]
    return line


if __name__ == "__main__":
    print(write_golden())
