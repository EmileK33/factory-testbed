"""Read CSV text produced by ``src.export_csv.render_export`` back into records.

See ``src/export_csv.py`` for the encoding (a JSON scalar/array per cell, rows delimited
by the stdlib ``csv`` module) and the six-column contract. ``parse_export`` takes its
column names from the file's own header row rather than importing ``FIELDNAMES``, so it
has no import-time dependency on ``src.export_csv``.
"""

from __future__ import annotations

import csv
import io
import json


def _decode_cell(header: str, row_index: int, text: str) -> object:
    """Decode one cell's JSON text, with a clear, located error on failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"export row {row_index}, column {header!r}: not valid JSON ({text!r})"
        ) from exc


def parse_export(text: str) -> list[dict]:
    """Return the records ``render_export`` produced *text* from.

    Equality with the original rows is on the decoded dicts, not on the CSV text: a value
    that left as an ``int`` comes back as an ``int``, and ``tags`` comes back as a ``list``
    of the same strings in the same order.

    Blank lines (for example a stray trailing newline) are skipped rather than turned into
    a spurious empty record. A data row whose column count does not match the header raises
    ``ValueError`` rather than silently zipping to the shorter length -- a quietly truncated
    dict is worse than a loud failure for a codec that promises to be lossless.
    """
    buf = io.StringIO(text, newline="")
    rows = [row for row in csv.reader(buf) if row]
    if not rows:
        return []
    header, data_rows = rows[0], rows[1:]

    records = []
    for row_index, data_row in enumerate(data_rows, start=1):
        if len(data_row) != len(header):
            raise ValueError(
                f"export row {row_index}: expected {len(header)} columns, "
                f"got {len(data_row)}"
            )
        records.append(
            {
                field: _decode_cell(field, row_index, cell)
                for field, cell in zip(header, data_row)
            }
        )
    return records
