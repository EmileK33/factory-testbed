"""Helpers for the feed's packed columns."""

from __future__ import annotations

import csv


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter. That is exactly the shape
    ``csv`` already parses, so a single line is handed to ``csv.reader``
    rather than re-deriving the quoting rules with a regex: a regex split on
    every comma (quoted or not) cannot tell a separator from a comma inside a
    quoted tag without reimplementing the same escaping rules ``csv`` already
    gets right.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. A column that is already a sequence is already split and passes
    through; anything else yields no tags rather than raising, because
    ``check_record()`` promises a normalised record or ``None`` and cannot keep
    that promise if this throws. Passing this function its own output returns
    that output unchanged.
    """
    if isinstance(raw, (list, tuple)):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    if not isinstance(raw, str) or not raw:
        return []
    try:
        row = next(csv.reader([raw], skipinitialspace=True))
    except csv.Error:
        return []
    return [part.strip() for part in row if part.strip()]
