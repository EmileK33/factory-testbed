"""Regenerate the committed JSON report artifact.

Run from the repository root::

    python -m tools.write_golden_json
"""

from __future__ import annotations

from pathlib import Path

from src.report_json import render_report_json

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "report.golden.json"


def write_golden_json(path: str | Path | None = None) -> Path:
    """Render the JSON report and write it to *path*, returning where it landed.

    The newline is pinned so the artifact is byte-identical on every platform;
    ``tests/test_golden_json.py`` compares bytes, not lines.
    """
    target = Path(path) if path is not None else GOLDEN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_report_json())
    return target


if __name__ == "__main__":
    print(write_golden_json())
