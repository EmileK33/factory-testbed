"""Helpers for the feed's packed columns."""

from __future__ import annotations

import csv
import io


def parse_tags(raw: str | None) -> list[str]:
    """Split the feed's ``tags`` column into individual tags.

    The column is a comma-separated list; a tag containing a comma is wrapped
    in double quotes by the upstream exporter. Parsing goes through
    ``csv.reader`` (the standard tool for quoted, comma-separated values) so a
    quoted comma stays inside its tag instead of splitting it in two.

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
    # csv.reader is itself an iterator over physical lines, so a stray literal
    # newline in the column (unquoted, and therefore not part of this contract)
    # yields more than one row rather than raising or silently truncating the
    # rest of the column; every row's fields are kept.
    #
    # csv.reader still raises csv.Error on input it never anticipated: an
    # unquoted bare "\r" ("new-line character seen in unquoted field") or a
    # field past its internal size limit ("field larger than field limit").
    # Both are just malformed tags data, not a reason to break the promise
    # this function makes above -- string in, list out, never a raise.
    try:
        fields = [
            field for row in csv.reader(io.StringIO(raw), skipinitialspace=True) for field in row
        ]
    except csv.Error:
        return []
    return [field.strip() for field in fields if field.strip()]
