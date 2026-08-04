"""Render settlement records as CSV text.

Each cell is stored as a JSON scalar/array (``json.dumps``), and the row itself is
delimited and quoted by the stdlib ``csv`` module. Composing two already-correct stdlib
codecs -- rather than inventing a sentinel scheme of our own -- is what makes ``None``,
``""``, and ``[]`` mutually distinguishable on the wire, and preserves ``int`` vs ``str``
vs ``list`` losslessly, for arbitrary string content (including values containing the
delimiter or a quote character). See ``src/import_csv.py`` for the read-back side and
``artifacts/export.golden.csv`` for the committed artifact this renders.

Column contract: exactly six columns -- ``src.report.REPORTED_FIELDS`` (``"id"``,
``"name"``, ``"region"``, ``"amount"``, ``"currency"``), in that order, followed by
``"tags"``. ``render_export(rows)``, given an explicit ``rows`` argument, reads precisely
those six columns from each row and nothing else: any other key present on an input dict
(for example a raw feed row's ``"status"``) is **not** exported and will not reappear from
``parse_export``. This module never validates a record -- that is ``src.validate.
check_record``'s job; ``render_export(rows)`` exports exactly the rows it is given.
"""

from __future__ import annotations

import csv
import io
import json

from src.records import load_records
from src.report import REPORTED_FIELDS
from src.validate import check_record

# The six exported columns, in the required order: the report's fields, then tags last.
FIELDNAMES = tuple(REPORTED_FIELDS) + ("tags",)


def _encode_cell(field: str, value: object) -> str:
    """Encode one column's value as a JSON scalar/array, with a clear error on failure."""
    try:
        return json.dumps(value)
    except TypeError as exc:
        raise TypeError(
            f"export column {field!r}: value {value!r} is not JSON-serialisable"
        ) from exc


def render_export(records: list[dict] | None = None) -> str:
    """Return *records* as CSV text (default: the live feed's accepted records).

    With no argument, loads the live feed via ``src.records.load_records`` and exports the
    records ``src.validate.check_record`` accepts, in feed order; rejected records are not
    exported.

    Given an explicit list, exports exactly those rows, as given -- this path does not call
    ``check_record``; validation belongs to the feed-loading path above. Only the six
    ``FIELDNAMES`` columns are read from each row (see module docstring); any other key is
    silently ignored, not exported.

    The line ending is ``\\n``, pinned, on every platform.
    """
    if records is None:
        raw = load_records()
        rows = [checked for checked in (check_record(row) for row in raw) if checked]
    else:
        rows = records

    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(FIELDNAMES)
    for row in rows:
        writer.writerow([_encode_cell(field, row.get(field)) for field in FIELDNAMES])
    return buf.getvalue()
