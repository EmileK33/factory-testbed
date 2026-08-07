"""Helpers for the feed's packed columns."""

from __future__ import annotations

import csv


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter. Parsed with ``csv.reader``
    (not a regex split) so a quoted comma stays inside its tag instead of
    being treated as a separator.

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
        rows = list(csv.reader([raw], skipinitialspace=True))
    except csv.Error:
        return []
    fields = rows[0] if rows else []
    return [part.strip() for part in fields if part.strip()]
