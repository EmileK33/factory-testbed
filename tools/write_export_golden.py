"""Regenerate the committed CSV export artifact.

Run from the repository root::

    python -m tools.write_export_golden
"""

from __future__ import annotations

from pathlib import Path

from src.export_csv import render_export

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "export.golden.csv"


def write_export_golden(path: str | Path | None = None) -> Path:
    """Render the export and write it to *path*, returning where it landed.

    The newline is pinned so the artifact is byte-identical on every platform;
    ``tests/test_export.py`` compares bytes, not lines.
    """
    target = Path(path) if path is not None else GOLDEN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_export())
    return target


if __name__ == "__main__":
    print(write_export_golden())
