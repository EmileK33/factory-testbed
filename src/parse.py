"""Helpers for the feed's packed columns."""

from __future__ import annotations

import csv


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter. A regex split on every comma
    cannot tell a separator comma from one inside a quoted tag, so this uses
    the standard library's CSV reader (a real parser for exactly this quoting
    rule) instead of layering another regex on the problem.

    A feed row is free-form JSON, so the column is not guaranteed to be a
    string. A column that is already a sequence is already split and passes
    through; anything else yields no tags rather than raising, because
    ``check_record()`` promises a normalised record or ``None`` and cannot keep
    that promise if this throws. Passing this function its own output returns
    that output unchanged. An oversized column (past ``csv``'s field size
    limit) also yields no tags rather than raising, for the same reason.
    """
    if isinstance(raw, (list, tuple)):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    if not isinstance(raw, str) or not raw:
        return []
    try:
        fields = next(csv.reader([raw], skipinitialspace=True), [])
    except csv.Error:
        return []
    return [field.strip() for field in fields if field.strip()]
